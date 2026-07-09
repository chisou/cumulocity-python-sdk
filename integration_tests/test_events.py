# Copyright (c) 2026 Christoph Souris
import asyncio
import logging
import os
import random
import tempfile
from datetime import timedelta
from io import BytesIO

import pytest

from pyc8y.client import CumulocityClient
from pyc8y.model import Device
from pyc8y.model.event import Event
from pyc8y.model.model_util import now_datetime

from util.testing_util import create_random_name


@pytest.fixture(scope='module')
async def sample_events(live_c8y: CumulocityClient, session_device: Device, module_factory) -> list[Event]:
    """Provide a set of sample Event instances."""
    typename = create_random_name()
    now = now_datetime()

    return [
        await module_factory(
            Event(type=f'{typename}_{i}', text=f'{typename} text', source=session_device.id,
                  time=now + timedelta(minutes=i))
        )
        for i in range(1, 6)
    ]


async def test_CRUD(live_c8y: CumulocityClient, session_device: Device):  # noqa (case)
    """Verify that basic CRUD functionality works."""

    typename = create_random_name()
    event = Event(live_c8y, type=typename, text=f'{typename} text', time='now', source=session_device.id)

    created_event = await event.create()
    try:
        # 1) assert correct creation
        assert created_event.id
        assert created_event.type == typename
        assert typename in created_event.text
        assert created_event.time
        assert created_event.creation_time

        # 2) update updatable fields
        created_event.text = f'{typename} updated'
        updated_event = await created_event.update(copy=True)
        assert updated_event.text == created_event.text

        # 3) use apply_to
        model_event = Event(live_c8y, text='some text')
        await model_event.apply_to(created_event.id)
        updated_event = await live_c8y.events.get(created_event.id)
        assert updated_event.text == 'some text'

    finally:
        await created_event.delete()

    # 4) assert deletion
    with pytest.raises(KeyError) as e:
        await live_c8y.events.get(created_event.id)
        assert created_event.id in str(e)


async def test_CRUD_2(live_c8y: CumulocityClient, session_device: Device):  # noqa (case)
    """Verify that basic CRUD functionality via the API works."""

    typename = create_random_name()
    event1 = Event(live_c8y, time="now", type=typename, text=f'{typename} text', source=session_device.id)
    event2 = Event(live_c8y, time="now", type=typename, text=f'{typename} text', source=session_device.id)

    # 1) create multiple events and read from Cumulocity
    await live_c8y.events.create(event1, event2)
    events = await live_c8y.events.get_all(type=typename)
    event_ids = [e.id for e in events]
    assert len(events) == 2

    try:
        # 2) assert correct creation
        for event in events:
            assert event.id
            assert event.type == typename
            assert typename in event.text
            assert event.time
            assert event.creation_time

        # 3) update updatable fields
        for event in events:
            event.text = 'new text'
        await live_c8y.events.update(*events)
        events = await live_c8y.events.get_all(type=typename)
        assert len(events) == 2

        # 4) assert updates
        for event in events:
            assert event.text == 'new text'

        # 5) apply updates via Event object
        model = Event(text='another update', simple_attribute='value')
        await live_c8y.events.apply_to(model, *event_ids)

        events = await live_c8y.events.get_all(type=typename)
        assert len(events) == 2
        assert all(e.text == 'another update' for e in events)

        # 6) apply updates via dict
        await live_c8y.events.apply_to({'text': 'updated text', 'add_info': 'yes'}, *event_ids)

        events = await live_c8y.events.get_all(type=typename)
        assert len(events) == 2
        assert all(e.text == 'updated text' for e in events)
        assert all(e['add_info'] == 'yes' for e in events)

    finally:
        await live_c8y.events.delete(*event_ids)

    # 7) assert deletion
    assert not await live_c8y.events.get_all(type=typename)


async def test_get_last(live_c8y: CumulocityClient, session_device: Device):
    """Verify that get_last returns the most recent matching event."""
    typename = create_random_name()
    device_id = session_device.id
    now = now_datetime()
    events = await asyncio.gather(*[
        Event(live_c8y, type=typename, text=f'Event{i}', source=device_id, time=now + timedelta(minutes=i)).create()
        for i in range(3)
    ])

    try:
        last = await live_c8y.events.get_last(type=typename, source=session_device.id)
        assert last is not None
        assert last.id == events[-1].id
    finally:
        await live_c8y.events.delete_by(type=typename, source=session_device.id)


async def test_filter_by_update_time(live_c8y: CumulocityClient, session_device: Device, sample_events: list[Event]):
    """Verify that filtering by lastUpdatedTime works as expected."""

    event = sample_events[0]

    updated_datetimes = [a.update_datetime for a in sample_events]
    updated_datetimes.sort()
    pivot = updated_datetimes[len(updated_datetimes) // 2]

    before_events = await live_c8y.events.get_all(source=event.source, updated_before=pivot)
    after_events = await live_c8y.events.get_all(source=event.source, updated_after=pivot, reverse=True)
    last_event_before = await live_c8y.events.get_last(source=event.source, updated_before=pivot)
    last_event_after = await live_c8y.events.get_last(source=event.source, updated_after=pivot)

    # upper boundary is exclusive (before/to does not include pivot)
    before_datetimes = [x for x in updated_datetimes if x < pivot]
    assert sorted(a.update_datetime for a in before_events) == sorted(before_datetimes)
    assert last_event_before.update_datetime == max(before_datetimes)

    # lower boundary is inclusive (after/from includes pivot)
    after_datetimes = [x for x in updated_datetimes if x >= pivot]
    assert sorted(a.update_datetime for a in after_events) == sorted(after_datetimes)
    assert last_event_after.update_datetime == max(after_datetimes)


async def test_select(live_c8y: CumulocityClient, sample_events: list[Event]):
    """Verify that selecting events works as expected."""

    # 1) client-side filtering
    event_1 = random.choice(sample_events)
    results = await live_c8y.events.get_all(source=event_1.source, include=f"type == '{event_1.type}'")
    assert results[0].id == event_1.id

    # 2) type/source filter
    assert (await live_c8y.events.get_all(type=event_1.type, source=event_1.source))[0].text == event_1.text


async def test_CRUD_attachments(live_c8y: CumulocityClient, session_device: Device, sample_events: list[Event]):  # noqa (case)
    """Verify that creating, reading, updating and deleting of an
    event attachment works as expected."""

    logging.basicConfig(level=logging.INFO)

    event = sample_events[0]
    random_text_1 = create_random_name().encode('utf-8')
    random_text_2 = create_random_name().encode('utf-8')

    # add a binary attachment via filename
    with tempfile.NamedTemporaryFile(delete=False) as file:
        try:
            file.write(random_text_1)
            file.close()
            await event.create_attachment(file=file.name, content_type='text/plain')
        finally:
            os.unlink(file.name)

    # refresh event object
    event = await live_c8y.events.get(event.id)
    assert event.has_attachment()

    # download and verify
    assert (await event.download_attachment()).content == random_text_1

    # update attachment via file-like object
    await event.update_attachment(file=BytesIO(random_text_2))

    # verify change
    assert (await event.download_attachment()).content == random_text_2

    # remove attachment
    await event.delete_attachment()
    event = await live_c8y.events.get(event.id)
    assert not event.has_attachment()


async def test_CRUD_attachments_2(live_c8y: CumulocityClient, session_device: Device, sample_events: list[Event]):  # noqa (case)
    """Verify that creating, reading, updating and deleting of an
    event attachment via the API works as expected."""

    event = sample_events[0]
    random_text_1 = create_random_name().encode('utf-8')
    random_text_2 = create_random_name().encode('utf-8')

    # add a binary attachment via filename
    with tempfile.NamedTemporaryFile(delete=False) as file:
        try:
            file.write(random_text_1)
            file.close()
            await live_c8y.events.create_attachment(event.id, file=file.name, content_type='text/plain')
        finally:
            os.unlink(file.name)

    # refresh and verify
    event = await live_c8y.events.get(event.id)
    assert (await live_c8y.events.download_attachment(event.id)).content == random_text_1

    # update attachment via file-like object
    await live_c8y.events.update_attachment(event.id, file=BytesIO(random_text_2))

    # verify change
    assert (await live_c8y.events.download_attachment(event.id)).content == random_text_2

    # remove attachment
    await live_c8y.events.delete_attachment(event.id)
    event = await live_c8y.events.get(event.id)
    assert not event.has_attachment()
