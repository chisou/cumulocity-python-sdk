import asyncio
import logging
import time
from typing import Callable, Self, Awaitable

from pyc8y.app import MultiTenantCumulocityApp


class SubscriptionListener:
    """Multi-tenant subscription listener.

    Polls a MultiTenantCumulocityApp for subscriber changes and invokes
    registered callbacks when tenants subscribe or unsubscribe.

    Note: Not thread-safe, expected to run in async code.
    """

    _n = 0

    def __init__(
        self,
        app: MultiTenantCumulocityApp,
        callback: Callable[[set[str]], Awaitable[None]] | None = None,
        sequential: bool = False,
        polling_interval: float = 3600,
        startup_delay: float = 60,
    ):
        """Create a subscription listener.

        Args:
            app (MultiTenantCumulocityApp): The Cumulocity application
                managing subscribers.
            callback (Callable): an async callback function to be invoked
                when the subscribers change; Use the `add_callback` function
                to add callbacks for individually added/removed subscribers.
            sequential (bool): If True, callbacks run sequentially. Otherwise
                (default) callbacks run concurrently as asyncio tasks.
            polling_interval (float): How often to poll for changes.
            startup_delay (float): How many seconds to wait after a
                subscriber change before invoking the callbacks.
        """
        instance_id = f"[{SubscriptionListener._n}]" if SubscriptionListener._n > 0 else ""
        SubscriptionListener._n += 1
        self._instance_name = type(self).__name__ + instance_id
        self._log = logging.getLogger(__name__ + instance_id)
        self.app = app
        self.polling_interval = polling_interval
        self.startup_delay = startup_delay
        self.callbacks: list[Callable] = [callback] if callback else []
        self.callbacks_on_add: list[Callable] = []
        self.callbacks_on_remove: list[Callable] = []
        self._lock = asyncio.Lock() if sequential else None
        self._listen_task: asyncio.Task | None = None
        self._callback_tasks: set[asyncio.Task] = set()
        self._stop_event = asyncio.Event()

    async def __aenter__(self) -> Self:
        self.start()
        return self

    async def __aexit__(self, *args):
        self.stop()
        if self._listen_task:
            await self._listen_task

    def add_callback(
        self,
        callback: Callable[[str | set[str]], None],
        when: str = "any",
    ) -> Self:
        """Add a callback for subscription changes.

        Args:
            callback: Async function invoked on subscription changes. Receives
                a single tenant ID (str) for 'added'/'removed' events, or the
                full set of current subscriber IDs for 'any'/'always'.
            when: When to invoke the callback — 'added', 'removed', or
                'any'/'always' (default).

        Returns:
            self, to support chaining.
        """
        if when in {"always", "any"}:
            return self.on_change(callback)
        elif when == "added":
            return self.on_add(callback)
        elif when == "removed":
            return self.on_remove(callback)
        else:
            raise ValueError(f"Invalid activation mode: {when}")

    def on_add(self, callback: Callable[[str], Awaitable[None]] ) -> Self:
        """Add a callback for added subscriptions.

        Args:
            callback: Async function invoked on subscription changes. Receives
                the tenant ID (str) of the added subscriber.

        Returns:
            self, to support chaining.
        """
        self.callbacks_on_add.append(callback)
        return self

    def on_remove(self, callback: Callable[[str], Awaitable[None]] ) -> Self:
        """Add a callback for removed subscriptions.

        Args:
            callback: Async function invoked on subscription changes. Receives
                the tenant ID (str) of the removed subscriber.

        Returns:
            self, to support chaining.
        """
        self.callbacks_on_remove.append(callback)
        return self

    def on_change(self, callback: Callable[[set[str]], Awaitable[None]] ) -> Self:
        """Add a callback for changed subscriptions.

        callback: Async function invoked on subscription changes. Receives
            the full set of current subscriber IDs.

        Returns:
            self, to support chaining.
        """
        self.callbacks.append(callback)
        return self

    async def listen(self):
        """Run the subscription polling loop.

        Blocks until stop() is called or the task is cancelled.
        """
        if not self._listen_task:
            self._listen_task = asyncio.current_task()
        self._stop_event.clear()
        self._log.debug("Listener started.")

        async def serialized(cr):
            assert self._lock is not None
            async with self._lock:
                await cr

        async def invoke(fun, arg):

            def on_done(task):
                self._callback_tasks.discard(task)
                if not task.cancelled() and task.exception():
                    self._log.error(f"Uncaught exception in callback: {task.exception()}", exc_info=task.exception())

            if self._log.isEnabledFor(logging.DEBUG):
                self._log.debug(f"Invoking callback: {fun.__module__}.{fun.__name__}")
            coro = serialized(fun(arg)) if self._lock else fun(arg)
            callback_task = asyncio.create_task(coro)
            self._callback_tasks.add(callback_task)
            callback_task.add_done_callback(on_done)

        try:
            last_subscribers: set[str] = set()
            while not self._stop_event.is_set():
                loop_start = time.monotonic()

                current_subscribers = set(await self.app.get_subscribers())
                added = current_subscribers - last_subscribers
                removed = last_subscribers - current_subscribers

                for tenant_id in removed:
                    self._log.info(f"Tenant subscription removed: {tenant_id}.")
                    for cb in self.callbacks_on_remove:
                        await invoke(cb, tenant_id)

                if added and self.startup_delay:
                    elapsed = time.monotonic() - loop_start
                    delay = self.startup_delay - elapsed
                    if delay > 0:
                        await asyncio.sleep(delay)

                for tenant_id in added:
                    self._log.info(f"Tenant subscription added: {tenant_id}.")
                    for cb in self.callbacks_on_add:
                        await invoke(cb, tenant_id)

                if added or removed:
                    self._log.info(f"Current subscriptions: {', '.join(current_subscribers) or 'None'}.")
                    for cb in self.callbacks:
                        await invoke(cb, current_subscribers)

                last_subscribers = current_subscribers

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.polling_interval)
                    break  # stop() was called
                except asyncio.TimeoutError:
                    pass  # interval elapsed, poll again

        except Exception as e:
            self._log.error(f"Uncaught exception during listen: {e}", exc_info=e)
        finally:
            pending = self.get_callbacks()
            if pending:
                self._log.debug(f"Awaiting {len(pending)} ending callbacks.")
                await asyncio.gather(*pending)
        self._log.debug("Listener ended.")

    def start(self) -> asyncio.Task:
        """Start the listener as an asyncio Task.

        Returns:
            The created asyncio Task.
        """
        task = asyncio.create_task(self.listen(), name=self._instance_name)
        self._listen_task = task
        return task

    def stop(self):
        """Signal the listener to stop.

        Returns immediately without awaiting the listener to finish.
        """
        self._stop_event.set()

    def get_callbacks(self) -> list[asyncio.Task]:
        """Return currently running (not yet done) callback tasks."""
        return [t for t in self._callback_tasks if not t.done()]
