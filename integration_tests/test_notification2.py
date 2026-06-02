# Copyright (c) 2026 Christoph Souris

# pylint: disable=protected-access

import asyncio
import contextlib
import logging
import re
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

import coolname
import pytest

from pyc8y.client import CumulocityClient
from pyc8y.model import (
    Device,
    ManagedObject,
    Alarm,
    Event,
    Measurement,
    Operation,
    Value,
)
from pyc8y.model.alarm import AlarmSeverity
from pyc8y.notification2 import Listener, QueueListener, Subscription
from pyc8y.notification2.listener import Message
from tests.utils import assert_in_any, assert_no_failures

from util.testing_util import create_random_name


def build_subscription_name(name: str) -> str:
    return f"{re.sub(r'[-_]', '', name)}Subscription"


@pytest.fixture(scope="function", name="sample_object")
async def fix_sample_object(live_c8y: CumulocityClient, safe_create):
    """Provide a sample managed object, automatically removed after the test."""
    name = create_random_name()
    mo = await safe_create(ManagedObject(live_c8y, name=name, type=f"test_{name}"))
    yield mo


@pytest.fixture(scope="function", name="sample_subscription")
async def fix_sample_subscription(sample_object):
    """Provide a "catch-all" subscription for a sample object."""
    sub = await Subscription(
        c8y=sample_object.c8y,
        name=build_subscription_name(sample_object.name),
        context=Subscription.Context.MANAGED_OBJECT,
        api_filter=["*"],
        source_id=sample_object.id,
    ).create()

    yield sub

    with contextlib.suppress(Exception):
        await sub.delete()


async def test_subscription_deletion(live_c8y: CumulocityClient, safe_create):
    """Verify that a subscription is removed with the corresponding managed object."""
    mo_name = create_random_name()
    mo = await safe_create(ManagedObject(live_c8y, name=mo_name, type=f"test_{mo_name}"))

    await Subscription(
        live_c8y,
        name=build_subscription_name(mo_name),
        context=Subscription.Context.MANAGED_OBJECT,
        source_id=mo.id,
    ).create()

    assert await live_c8y.subscriptions.get_count(source=mo.id) == 1
    await mo.delete()
    await asyncio.sleep(1)
    assert await live_c8y.subscriptions.get_count(source=mo.id) == 0


@pytest.fixture(name="object_tree_builder")
def fix_object_tree_builder(live_c8y: CumulocityClient, safe_create):
    """Provide a builder function which creates a root object with 3 children
    (asset, device, and addition)."""

    async def build():
        mo_name = coolname.generate_slug(3)
        type_name = f"test_{mo_name}"
        mo = await safe_create(ManagedObject(live_c8y, name=mo_name, type=type_name))
        child_asset = await safe_create(ManagedObject(live_c8y, name=f"{mo_name}_child_asset", type=type_name))
        child_device = await safe_create(Device(live_c8y, name=f"{mo_name}_child_device", type=type_name))
        child_addition = await safe_create(ManagedObject(live_c8y, name=f"{mo_name}_child_addition", type=type_name))
        await mo.add_child_asset(child_asset)
        await mo.add_child_device(child_device)
        await mo.add_child_addition(child_addition)
        return await mo.reload()

    return build


@pytest.mark.parametrize(
    "api_filters, expected",
    [
        ("*", "M,E,EwC,A,AwC,MO,O"),
        ("M", "M"),
        ("E", "E"),
        ("EwC", "E,EwC"),
        ("A", "A"),
        ("AwC", "A,AwC"),
        ("MO", "MO"),
    ],
    ids=[
        "*",
        "measurements",
        "events",
        "events+children",
        "alarms",
        "alarms+children",
        "managedObjects",
    ],
)
async def test_api_filters(live_c8y: CumulocityClient, sample_object, api_filters, expected):
    """Verify that API filters work as expected.

    This test creates a subscription with selected API filters and performs
    a couple of corresponding changes. It then matches the received
    notifications against expectations.
    """
    apis = {
        "*": "*",
        "M": "measurements",
        "E": "events",
        "A": "alarms",
        "EwC": "eventsWithChildren",
        "AwC": "alarmsWithChildren",
        "O": "operations",
        "MO": "managedobjects",
    }
    expected = [apis[x] for x in expected.split(",")]
    api_filters = [apis[x] for x in api_filters.split(",")]

    mo = sample_object
    mo["c8y_IsDevice"] = {}
    mo["com_cumulocity_model_Agent"] = {}
    await mo.update()
    sub = await Subscription(
        live_c8y,
        name=build_subscription_name(mo.name),
        context=Subscription.Context.MANAGED_OBJECT,
        api_filter=api_filters,
        source_id=mo.id,
    ).create()

    notifications: list[Message] = []

    async def receive_notification(m: Message):
        notifications.append(m)
        await m.ack()

    # (1) Create listener and start listening
    listener = Listener(live_c8y, subscription_name=sub.name, auto_ack=False)
    listener.start(receive_notification)
    try:
        await asyncio.sleep(3)  # ensure connection

        # (2) apply updates
        now = datetime.now(timezone.utc)
        m = Measurement(live_c8y, type="c8y_TestMeasurement", source=mo.id, time=now)
        m["c8y_TestMeasurement"] = {"value": Value(1, "")}
        m_id = (await m.create()).id
        e_id = (await Event(live_c8y, type="c8y_TestEvent", source=mo.id, time=now, text="text").create()).id
        a_id = (
            await Alarm(
                live_c8y, type="c8y_TestAlarm", source=mo.id, time=now, text="text", severity=AlarmSeverity.WARNING
            ).create()
        ).id
        o_id = (await Operation(live_c8y, device_id=mo.id, c8y_Operation={}).create()).id
        await live_c8y.inventory.apply_to({"some_tag": {}}, mo.id)

        await asyncio.sleep(1)
        # collect message types from source URL
        types = {n.source.split("/")[2] for n in notifications}
        for e in expected:
            assert_in_any(e, types)
        ids = {n.json["id"] for n in notifications}
        if "measurements" in expected:
            assert m_id in ids
        if "events" in expected:
            assert e_id in ids
        if "alarms" in expected:
            assert a_id in ids
        if "operations" in expected:
            assert o_id in ids
    finally:
        listener.stop()
        await listener.wait()
        with contextlib.suppress(Exception):
            await sub.delete()


async def test_token_timeout(caplog, live_c8y: CumulocityClient, sample_subscription):
    """Verify that token timeout is handled properly.

    This test configures the listener to use a one-minute token timeout. A
    single change is applied to the monitored managed object to verify that
    the setup was successful. The test then waits for the token to time out
    before stopping the listener.

    -> notification was handled
    -> two tokens were generated
    """
    caplog.set_level(logging.INFO)

    obj_id = sample_subscription.source_id
    callback = Mock()

    async def async_callback(msg):
        callback()

    listener = Listener(
        live_c8y,
        subscription_name=sample_subscription.name,
        auto_ack=True,
    )
    listener.token_validity = 1  # minimize validity
    listener.start(async_callback)
    await asyncio.sleep(5)  # ensure connection
    token1 = listener._current_token
    try:
        await live_c8y.inventory.apply_to({"test_CustomFragment": {"num": 42}}, obj_id)
        await asyncio.sleep(20)  # wait for the token to expire
    finally:
        listener.stop()
        await listener.wait()
    token2 = listener._current_token

    # -> callback was invoked once
    callback.assert_called_once()
    # -> 2 tokens where generated
    assert token1 != token2
    # -> 2 corresponding log messages
    log_messages = [r.message for r in caplog.records]
    assert sum("Notification 2.0 token requested" in x for x in log_messages) == 2
    assert sum("cancelled" in x for x in log_messages) == 1
    assert_no_failures(caplog)


async def test_object_update_and_deletion(live_c8y: CumulocityClient, safe_create):
    """Verify that we can subscribe to managed object changes and they are received.

    This test creates a simple managed object and a corresponding subscription; the subscription
    limits the 'fragments to copy'. We then apply 2 changes, both should be received but only the
    expected fragment should be part of the notification body.

    Finally, the deletion of the object should also be received.
    """
    mo_name = create_random_name()
    mo = await safe_create(ManagedObject(live_c8y, name=mo_name, type=f"test_{mo_name}"))
    sub = await Subscription(
        live_c8y,
        name=build_subscription_name(mo.name),
        context=Subscription.Context.MANAGED_OBJECT,
        fragments=["test_AwaitedFragment"],
        source_id=mo.id,
    ).create()

    notifications = asyncio.Queue()

    async def receive_notification(m: Message):
        await notifications.put(m)
        await m.ack()

    listener = Listener(live_c8y, subscription_name=sub.name, auto_ack=False)
    listener.start(receive_notification)
    await asyncio.sleep(5)  # ensure connection

    # (1) apply first change, expected fragment
    await live_c8y.inventory.apply_to({"test_AwaitedFragment": {"num": 42}}, mo.id)
    # -> notification should appear
    m = await asyncio.wait_for(notifications.get(), timeout=5)
    assert notifications.empty()
    assert mo.id in m.source
    assert m.action == "UPDATE"
    # -> basic data AND expected fragment in payload
    assert m.json["id"] == mo.id
    assert m.json["name"] == mo.name
    assert m.json["type"] == mo.type
    assert m.json["test_AwaitedFragment"]["num"] == 42

    # (2) Apply 2nd change, different fragment
    await live_c8y.inventory.apply_to({"test_DifferentFragment": {"num": 42}}, mo.id)
    # -> notification should appear
    m = await asyncio.wait_for(notifications.get(), timeout=5)
    assert notifications.empty()
    assert mo.id in m.source
    assert m.action == "UPDATE"
    # -> basic data in payload
    assert m.json["id"] == mo.id
    assert m.json["name"] == mo.name
    assert m.json["type"] == mo.type
    # -> other fragment not in payload
    assert "test_AwaitedFragment" in m.json
    assert "test_DifferentFragment" not in m.json

    # (3) delete object tree
    await mo.delete_tree()
    # -> notification should appear
    m = await asyncio.wait_for(notifications.get(), timeout=5)
    assert notifications.empty()
    assert mo.id in m.source
    assert m.action == "DELETE"

    # (99) cleanup
    listener.stop()
    await listener.wait()
    with contextlib.suppress(Exception):
        await sub.delete()


async def test_child_updates(live_c8y: CumulocityClient, object_tree_builder):
    """Verify that updates to child objects are ignored."""
    root = await object_tree_builder()

    root_subscription = await Subscription(
        live_c8y,
        name=build_subscription_name(root.name),
        context=Subscription.Context.MANAGED_OBJECT,
        source_id=root.id,
    ).create()

    notified = asyncio.Event()

    async def receive_notification(m: Message):
        notified.set()
        await m.ack()

    listener = Listener(live_c8y, subscription_name=root_subscription.name, auto_ack=False)
    try:
        listener.start(receive_notification)
        await asyncio.sleep(5)  # ensure connection
        await live_c8y.inventory.apply_to(
            {"test_CustomFragment": {"num": 42}},
            *[x.id for x in root.child_assets],
            *[x.id for x in root.child_devices],
            *[x.id for x in root.child_additions],
        )
        await asyncio.sleep(2)
    finally:
        listener.stop()
        await listener.wait()
        with contextlib.suppress(Exception):
            await root_subscription.delete()

    assert not notified.is_set()


async def test_parent_updates(live_c8y: CumulocityClient, object_tree_builder):
    """Verify that updates to parent objects are ignored."""
    root = await object_tree_builder()

    children = root.child_assets + root.child_devices + root.child_additions
    child_subscriptions = [
        await Subscription(
            live_c8y,
            name=build_subscription_name(c.name),
            context=Subscription.Context.MANAGED_OBJECT,
            source_id=c.id,
        ).create()
        for c in children
    ]

    notifications: list[Message] = []

    async def receive_notification(m: Message):
        notifications.append(m)
        await m.ack()

    listeners = [Listener(live_c8y, subscription_name=s.name, auto_ack=False) for s in child_subscriptions]
    try:
        for listener in listeners:
            listener.start(receive_notification)
        await asyncio.sleep(5)  # ensure connection
        await live_c8y.inventory.apply_to({"test_CustomFragment": {"num": 42}}, root.id)
        await asyncio.sleep(2)
    finally:
        for listener in listeners:
            listener.stop()
        for listener in listeners:
            await listener.wait()
        for sub in child_subscriptions:
            with contextlib.suppress(Exception):
                await sub.delete()

    assert not notifications


def create_managed_object_subscription(c8y, mo):
    """Build a subscription for a managed object."""
    return Subscription(
        c8y,
        name=build_subscription_name(mo.name),
        context=Subscription.Context.MANAGED_OBJECT,
        source_id=mo.id,
    )


@pytest.mark.parametrize("shared", [True, False])
async def test_multiple_subscribers(caplog, live_c8y: CumulocityClient, sample_object, shared):
    """Verify that multiple subscribers/consumers can be created for a single subscription.

    This test creates a managed object and corresponding subscription as well as multiple
    listeners with shared/unique subscriber names. An update to the managed object should
    notify each of the subscribers if unique or just one of the subscribers if shared.
    """
    caplog.set_level(logging.INFO)

    mo = sample_object
    sub = await create_managed_object_subscription(live_c8y, mo).create()

    notifications: list[Message] = []

    async def receive_notification(m: Message):
        notifications.append(m)
        await m.ack()

    n_listeners = 3
    listeners = [
        Listener(
            live_c8y,
            subscription_name=sub.name,
            subscriber_name=f"{sub.name}{i if not shared else 0}",
            shared=shared,
            auto_ack=False,
        )
        for i in range(n_listeners)
    ]

    for listener in listeners:
        listener.start(receive_notification)
    try:
        await asyncio.sleep(5)  # ensure connection
        await live_c8y.inventory.apply_to({"test_CustomFragment": {"num": 42}}, mo.id)
        await asyncio.sleep(3)  # ensure processing
    finally:
        for listener in listeners:
            listener.stop()
        for listener in listeners:
            await listener.wait()
        with contextlib.suppress(Exception):
            await sub.delete()

    # -> there should be 1/3 messages for shared/not shared
    assert len(notifications) == (3 if not shared else 1)
    # -> all received notifications are identical
    assert len({n.raw for n in notifications}) == 1
    # -> if shared, there should be unsubscribed infos/warnings
    log_messages = [r.message for r in caplog.records]
    assert sum("unsubscribed." in x for x in log_messages) == (1 if shared else n_listeners)
    assert sum("could not be unsubscribed (assuming it was already unsubscribed)" in x for x in log_messages) == (
        n_listeners - 1 if shared else 0
    )
    assert sum("cancelled" in x for x in log_messages) == n_listeners
    assert_no_failures(caplog)


async def test_queue_listener(live_c8y: CumulocityClient, sample_object):
    """Verify that the queue listener works as expected."""
    mo = sample_object
    sub = await create_managed_object_subscription(live_c8y, mo).create()

    q = asyncio.Queue()
    listener = QueueListener(c8y=live_c8y, subscription_name=sub.name, queue=q)

    listener.start()
    try:
        await asyncio.sleep(5)  # ensure connection
        await live_c8y.inventory.apply_to({"test_CustomFragment": {"num": 42}}, mo.id)
        msg = await asyncio.wait_for(q.get(), timeout=5)
        assert msg.json["test_CustomFragment"]["num"] == 42
    finally:
        listener.stop()
        await listener.wait()
        with contextlib.suppress(Exception):
            await sub.delete()


async def test_subscriber_timeout(live_c8y: CumulocityClient, sample_object):
    """Verify that a conflict (HTTP 409) will lead to a regular reconnection attempt."""
    mo = sample_object
    sub = await create_managed_object_subscription(live_c8y, mo).create()
    l1 = Listener(live_c8y, subscription_name=sub.name, subscriber_name=sub.name, auto_ack=True, shared=False)
    l2 = Listener(live_c8y, subscription_name=sub.name, subscriber_name=sub.name, auto_ack=True, shared=False)

    receive_notification1 = AsyncMock()
    receive_notification2 = AsyncMock()

    try:
        # start 1st listener
        l1.start(receive_notification1)
        await asyncio.sleep(5)  # ensure creation
        await mo.apply({'test_CustomFragment': {'num': 1}})
        await asyncio.sleep(3)  # ensure processing
        assert receive_notification1.call_count == 1

        # start 2nd listener
        # -> l2 can't connect until the 1st is stopped
        # -> l1 is still responsible
        l2.start(receive_notification2)
        l2.retry_max_delay = 0.5  # l2 should retry frequently
        await asyncio.sleep(5)  # ensure creation
        await mo.apply({'test_CustomFragment': {'num': 2}})
        await asyncio.sleep(3)  # ensure processing
        assert receive_notification1.call_count == 2
        assert receive_notification2.call_count == 0

        # close the connection of the first listener
        # -> 2nd should connect
        l1._create_connection = AsyncMock(side_effect=lambda: asyncio.sleep(30), return_value=None)  # l1 will not be able to reconnect
        await l1._connection.close()
        await asyncio.sleep(5)  # ensure connection of l2
        await mo.apply({'test_CustomFragment': {'num': 3}})
        await asyncio.sleep(5)  # ensure processing
        assert receive_notification1.call_count == 2
        assert receive_notification2.call_count == 1

    finally:
        with contextlib.suppress(Exception):
            l1.stop()
            await l1.wait()
        with contextlib.suppress(Exception):
            l2.stop()
            await l2.wait()