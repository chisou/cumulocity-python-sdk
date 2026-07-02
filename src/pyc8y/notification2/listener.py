# Copyright (c) 2026 Christoph Souris

import asyncio
import contextlib
import json as js
import logging
import uuid
from itertools import count
from typing import Callable, Awaitable

import aiohttp

from pyc8y.auth import JWT
from pyc8y.client import CumulocityClient


class Message:
    """Represents a Notification 2.0 message."""

    def __init__(self, listener: "Listener", payload: str):
        """Create a new Notification 2.0 message.

        Args:
            listener (Listener):  Reference to the originating listener
            payload (str):  Raw message payload
        """
        self.listener = listener
        self.raw = payload
        parts = payload.splitlines(keepends=False)
        assert len(parts) > 3
        self.id = parts[0]
        self.source = parts[1]
        self.action = parts[2]
        self.body = parts[len(parts) - 1]

    @property
    def json(self):
        """JSON representation (dict) of the message body."""
        return js.loads(self.body)

    async def ack(self):
        """Acknowledge the message."""
        await self.listener.ack(self.id)


class Listener(object):
    """Asynchronous Notification 2.0 listener.

    Notification 2.0 events are distributed via Pulsar topics, communicating
    via websockets.

    This class encapsulates the Notification 2.0 communication protocol,
    providing a standard callback mechanism.

    Note: Listening with callback requires some sort of parallelism. This
    listener is implemented in a non-blocking fashion using Python coroutines.

    See also: https://cumulocity.com/guides/reference/notifications/
    """

    _ids = count(0)  # instance's serial for logging

    def __init__(
            self,
            c8y: CumulocityClient,
            subscription_name: str,
            subscriber_name: str | None = None,
            consumer_name: str | None = None,
            shared: bool = False,
            auto_ack: bool = True,
            auto_unsubscribe: bool = True,
    ):
        """Create a new Listener.

        Args:
            c8y (CumulocityClient):  Cumulocity connection reference
            subscription_name (str):  Subscription name
            subscriber_name (str):  Subscriber (consumer) name; a sensible
                default is used when this is not defined.
            consumer_name (str):  Consumer name for shared subscriptions.
            shared (bool):  Whether this is a shared subscription.
            auto_ack (bool):  Whether to automatically acknowledge messages.
            auto_unsubscribe (bool):  Whether to automatically unsubscribe
                when the listener stops.
        """
        self._id = next(self._ids)
        self._log = logging.getLogger(f"{__name__}.Listener[{self._id}]")

        self.c8y = c8y
        self.subscription_name = subscription_name
        self.subscriber_name = subscriber_name or subscription_name
        self.consumer_name = consumer_name
        self.shared = shared
        self.auto_ack = auto_ack
        self.auto_unsubscribe = auto_unsubscribe
        self.signed_token = True
        # these are no constructor arguments, but allowed to change
        self.connect_timeout: int | None = None
        self.token_validity: float = 1440
        self.ping_interval: float = 60
        self.retry_interval: float = 0.1
        self.retry_rate: float = 1.5
        self.retry_max_delay: float = 30

        self._task = None
        self._connection = None
        self._current_token = None
        self._is_running = asyncio.Event()
        self._is_connected = asyncio.Event()
        self._stop_event = asyncio.Event()

    async def _create_token(self) -> str:
        token = await self.c8y.tokens.generate(
            subscription=self.subscription_name,
            subscriber=self.subscriber_name,
            shared=self.shared,
            signed=self.signed_token,
            expires=self.token_validity,
        )
        self._log.info(
            "New Notification 2.0 token requested for subscription %s, %s.",
            self.subscription_name,
            self.subscriber_name,
        )
        return token

    async def _create_connection(self) -> aiohttp.ClientWebSocketResponse:
        """Raises:
            aiohttp.ClientError: if the connection cannot be established.
            asyncio.TimeoutError: If the ws connection cannot be opened in time.
        """
        self._current_token = await self._create_token()
        # if shared, consumer names should be unique
        consumer = self.consumer_name  # user's choice is used
        if not consumer and self.shared:
            consumer = self.subscriber_name + uuid.uuid4().hex[:8]
        # a consumer name is used for shared subscribers only
        uri = self.c8y.tokens.build_websocket_uri(
            token=self._current_token,
            consumer=consumer if self.shared else None,
        )
        session = await self.c8y.session
        connection = await asyncio.wait_for(
            session.ws_connect(uri, heartbeat=self.ping_interval), timeout=self.connect_timeout
        )
        self._log.info(
            "Websocket connection established for subscription %s, %s.",
            self.subscription_name,
            self.subscriber_name,
        )
        return connection

    async def listen(self, callback: Callable[[Message], Awaitable[None]]):
        """Listen and handle messages.

        This function starts listening for new Notification 2.0 messages on
        the websocket channel. Each received message is wrapped in a `Message`
        object and forwarded to the callback function for handling.

        The messages are not automatically acknowledged. This can be done
        via the `Message` object's `ack` function by the callback function.

        Note: the callback function is invoked as a task and not awaited.

        This function will automatically handle the websocket communication
        including the authentication via tokens and reconnecting on
        connection loss. It will end when the listener is stopped using its
        `stop` function.
        """

        async def _callback(msg):
            try:
                await callback(msg)
                self._log.debug("Message %s processed.", msg.id)
                if self.auto_ack:
                    await msg.ack()
                    self._log.debug("Message %s acknowledged.", msg.id)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self._log.error("Callback failed with exception: %s", e, exc_info=e)

        if self._is_running.is_set():
            raise RuntimeError("Listener already started")
        self._task = asyncio.current_task()
        self._is_running.set()
        self._stop_event.clear()

        # outer connection loop
        connection_retry = 0
        while not self._stop_event.is_set():
            try:
                self._connection = await self._create_connection()
                self._is_connected.set()
                connection_retry = 0  # reset after successful connect
                # inner receive loop
                while not self._stop_event.is_set():
                    msg = await self._connection.receive()
                    if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.ERROR):
                        self._log.info("Websocket connection closed (type: %s).", msg.type.name)
                        break
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        self._log.debug("Received message: %s", msg.data)
                        await asyncio.create_task(_callback(Message(listener=self, payload=msg.data)))
                # connection was closed by the server; apply backoff before reconnecting
                if not self._stop_event.is_set():
                    connection_retry += 1
                    backoff_delay = self.retry_interval * self.retry_rate**connection_retry
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(
                            self._stop_event.wait(), timeout=min(backoff_delay, self.retry_max_delay)
                        )
            except asyncio.CancelledError:
                self._log.info("Subscriber %s cancelled. Stopping ...", self.subscriber_name)
                self._stop_event.set()
            except aiohttp.ClientConnectorSSLError as e:
                self._log.error("SSL connection failed: %s", e, exc_info=e)
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                self._log.info("Websocket connection failed: %s", e)
                connection_retry += 1
                backoff_delay = self.retry_interval * self.retry_rate**connection_retry
                with contextlib.suppress(TimeoutError):  # timeout is expected when not stopped
                    await asyncio.wait_for(self._stop_event.wait(), timeout=min(backoff_delay, self.retry_max_delay))
            finally:
                # close and clear connection
                self._is_connected.clear()
                if self._connection:
                    with contextlib.suppress(Exception):
                        await self._connection.close()
                self._connection = None

        self._is_running.clear()
        if self.auto_unsubscribe:
            await self.unsubscribe()

    def start(self, callback: Callable[[Message], Awaitable[None]]):
        """Start the listener.

        This function will start the listening process (`listen` function)
        and register the callback function to be invoked on every subscribed
        notification.

        Args:
            callback: Async function to be invoked on notifications

        Returns:
            Created listener task.
        """
        return asyncio.create_task(self.listen(callback))

    def stop(self):
        """Stop the listener."""
        self._stop_event.set()
        # still cancel the task to interrupt the blocking receive
        if self._task is not None:
            self._task.cancel()

    async def wait(self, timeout=None):
        """Wait for the listener task to finish.

        Args:
            timeout (int): The number of seconds to wait for the listener
                to finish. The listener will be cancelled if the timeout
                occurs.
        """
        if self._task:
            await asyncio.wait_for(self._task, timeout=timeout)

    async def unsubscribe(self):
        """Unsubscribe the listener.

        Manually unsubscribing is required if the listener wasn't created
        with `auto_unsubscribe=True`.

        See also https://cumulocity.com/api/core/#section/Overview/Consumers-and-tokens
        """
        try:
            token = self._current_token or await self._create_token()
            if JWT(token).get_valid_seconds() < 60:
                token = await self._create_token()
            self._current_token = token
            await self.c8y.tokens.unsubscribe(token)
            self._log.info("Subscriber %s unsubscribed.", self.subscriber_name)
        except ValueError:
            if not self.shared:
                self._log.error(
                    "Subscriber %s could not be unsubscribed (potentially data leak).",
                    self.subscriber_name,
                )
            else:
                self._log.info(
                    "Subscriber %s could not be unsubscribed (assuming it was already unsubscribed).",
                    self.subscriber_name,
                )
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._log.fatal(
                "Subscriber %s could not be unsubscribed (unknown error: %s).",
                self.subscriber_name, e, exc_info=e
            )

    async def send(self, payload: str):
        """Send a custom message.

        Args:
            payload (str):  Message payload to send.
        """
        self._log.debug("Sending message: %s", payload)
        await self._is_connected.wait()
        await self._connection.send_str(payload)
        self._log.debug("Message sent: %s", payload)

    async def ack(self, msg_id: str | None = None, payload: str | None = None):
        """Acknowledge a Notification 2.0 message.

        Either a valid Notification 2.0 message ID or payload needs to be
        provided. The message ID is extracted from the payload if necessary
        and sends it to the channel to signal the message handling
        completeness.

        Args:
            msg_id (str): Message ID to acknowledge.
            payload (str):  Raw Notification 2.0 message payload.

        See also:
            - Function `Message.ack` to acknowledge a specific Notification
              2.0 message directly.
            - `Listener` parameter `auto_ack=True` to automatically
              acknowledge a processed message
        """
        msg_id = msg_id or payload.splitlines()[0]
        # only attempt to ack if still connected (might not when stopping)
        if self._is_connected.is_set():
            await self.send(msg_id)
        else:
            self._log.warning("Message %s not acknowledged (connection lost).", msg_id)


class QueueListener(object):
    """Listener implementation that pushes notification messages into an
    asyncio queue which can be monitored and consumed."""

    def __init__(
            self,
            c8y: CumulocityClient,
            subscription_name: str,
            subscriber_name: str | None = None,
            consumer_name: str | None = None,
            shared: bool = False,
            auto_unsubscribe: bool = True,
            queue: asyncio.Queue | None = None,
    ):
        """Create a new QueueListener.

        Args:
            c8y (CumulocityClient):  Cumulocity connection reference
            subscription_name (str):  Subscription name
            subscriber_name (str):  Subscriber (consumer) name; a sensible
                default is used when this is not defined.
            consumer_name (str):  Consumer name for shared subscriptions.
            shared (bool):  Whether this is a shared subscription.
            auto_unsubscribe (bool):  Whether to automatically unsubscribe
                when the listener stops.
            queue (asyncio.Queue):  Queue to push messages into; a new one
                is created if not provided.
        """
        self.queue = queue or asyncio.Queue()
        self.listener = Listener(
            c8y=c8y,
            subscription_name=subscription_name,
            subscriber_name=subscriber_name,
            consumer_name=consumer_name,
            shared=shared,
            auto_ack=True,
            auto_unsubscribe=auto_unsubscribe,
        )

    def start(self):
        """Start the listener."""

        async def push_message(msg: Message):
            self.queue.put_nowait(msg)

        self.listener.start(push_message)

    def stop(self):
        """Stop the listener."""
        self.listener.stop()

    async def wait(self, timeout=None):
        """Wait for the listener task to finish.

        Args:
            timeout (int): The number of seconds to wait for the listener
                to finish. The listener will be cancelled if the timeout
                occurs.
        """
        await self.listener.wait(timeout=timeout)
