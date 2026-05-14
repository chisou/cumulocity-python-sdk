# Copyright (c) 2026 Christoph Souris

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyc8y.app import MultiTenantCumulocityApp, SubscriptionListener


def make_app(*subscriber_batches):
    """Build a mock app whose get_subscribers returns successive batches."""
    app = MagicMock(spec=MultiTenantCumulocityApp)
    app.get_subscribers = AsyncMock(side_effect=list(subscriber_batches))
    return app


async def test_sub_setting():
    """Verify that callbacks are invoked with the correct arguments and timing."""
    app = make_app(
        ["t1"],              # add t1
        ["t1", "t2", "t3"], # add t2, t3
        ["t2", "t3", "t4"], # remove t1, add t4
        ["t4"],             # remove t2, t3
    )
    listener = SubscriptionListener(app=app, polling_interval=0, startup_delay=0)

    added = set()
    async def added_fun(tenant_id):
        added.add(tenant_id)

    removed = set()
    async def removed_fun(tenant_id):
        removed.add(tenant_id)
        if tenant_id == "t2":
            listener.stop()

    always = []
    async def always_fun(tenant_ids):
        always.append(tenant_ids)

    listener.add_callback(added_fun, when="added")
    listener.add_callback(removed_fun, when="removed")
    listener.add_callback(always_fun)

    await listener.listen()

    assert added == {"t1", "t2", "t3", "t4"}
    assert removed == {"t1", "t2", "t3"}
    assert always == [
        {"t1"},
        {"t1", "t2", "t3"},
        {"t2", "t3", "t4"},
        {"t4"},
    ]


async def test_callback_tasks():
    """Verify that callbacks are dispatched as tasks and cleaned up on completion."""
    app = make_app(["t1"], [])
    listener = SubscriptionListener(app=app, polling_interval=0, startup_delay=0)

    added_mock = AsyncMock()

    async def removed_fun(_):
        listener.stop()

    listener.add_callback(added_mock, when="added")
    listener.add_callback(removed_fun, when="removed")

    await listener.listen()

    assert not listener.get_callbacks()
    assert not listener._callback_tasks
    added_mock.assert_called_once_with("t1")


async def test_serialized_callbacks():
    """Verify that serialize=True runs callbacks one at a time."""
    app = MagicMock(spec=MultiTenantCumulocityApp)
    app.get_subscribers = AsyncMock(return_value=["t1", "t2", "t3", "t4"])
    listener = SubscriptionListener(app=app, polling_interval=0.1, startup_delay=0, sequential=True)

    async def added_fun(_):
        listener.stop()
        await asyncio.sleep(1)

    listener.add_callback(added_fun, when="added")

    t0 = time.monotonic()
    await listener.listen()
    t1 = time.monotonic()

    # 4 callbacks, serialized, 1s each → ~4 seconds
    assert 4 < t1 - t0 < 5
    assert not listener.get_callbacks()


async def test_startup_delay():
    """Verify that the startup delay is honored before 'added' callbacks fire."""
    app = MagicMock(spec=MultiTenantCumulocityApp)
    app.get_subscribers = AsyncMock(return_value=["t1"])
    listener = SubscriptionListener(app=app, polling_interval=0.1, startup_delay=1)

    t0, t1 = 0.0, 0.0

    async def added_fun(_):
        nonlocal t1
        t1 = time.monotonic()
        listener.stop()

    listener.add_callback(added_fun, when="added")

    t0 = time.monotonic()
    await listener.listen()

    assert t1 - t0 > listener.startup_delay


async def test_listener_task():
    """Verify that start() creates a background task that can be awaited."""
    listen_run_time = 0.5

    app = MagicMock(spec=MultiTenantCumulocityApp)
    listener = SubscriptionListener(app=app)

    async def slow_listen():
        await asyncio.sleep(listen_run_time)

    listener.listen = slow_listen

    t0 = time.monotonic()
    task = listener.start()
    assert not task.done()

    await task
    t1 = time.monotonic()

    assert task.done()
    assert t1 - t0 >= listen_run_time


async def test_listener_task_timeout():
    """Verify that a running listener task can be cancelled after a timeout."""
    listen_run_time = 3

    app = MagicMock(spec=MultiTenantCumulocityApp)
    listener = SubscriptionListener(app=app)

    async def slow_listen():
        await asyncio.sleep(listen_run_time)

    listener.listen = slow_listen

    t0 = time.monotonic()
    task = listener.start()

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(asyncio.shield(task), timeout=0.1)

    assert not task.done()
    assert time.monotonic() - t0 < listen_run_time

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_listen_drains_callbacks():
    """Verify that listen() awaits all pending callbacks before returning."""
    callback_run_time = 1

    app = MagicMock(spec=MultiTenantCumulocityApp)
    app.get_subscribers = AsyncMock(return_value=["t1"])
    listener = SubscriptionListener(app=app, polling_interval=0.1, startup_delay=0)

    async def fun(_):
        listener.stop()
        await asyncio.sleep(callback_run_time)

    listener.add_callback(fun)

    t0 = time.monotonic()
    await listener.listen()
    t1 = time.monotonic()

    assert t1 - t0 >= callback_run_time
    assert not listener.get_callbacks()


async def test_multiple_tasks_in_parallel():
    """Verify that callbacks run concurrently by default."""
    app = MagicMock(spec=MultiTenantCumulocityApp)
    app.get_subscribers = AsyncMock(return_value=["t1"])
    listener = SubscriptionListener(app=app, polling_interval=0.1, startup_delay=0)

    callback_run_time = 1

    async def fun(_):
        listener.stop()
        await asyncio.sleep(callback_run_time)

    listener.add_callback(fun)
    listener.add_callback(fun)
    listener.add_callback(fun)

    t0 = time.monotonic()
    await listener.listen()
    t1 = time.monotonic()

    assert callback_run_time < t1 - t0 < callback_run_time + 0.5
