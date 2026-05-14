# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris

# pylint: disable=redefined-outer-name

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

from pyc8y.model.event import Event


@pytest.fixture(scope='function')
def sample_event() -> Event:
    """Provide a sample object for various tests."""
    return Event(type='type', text='text', time='2020-01-31T22:33:44Z', source='12345',
                 simple_string='string',
                 simple_int=123,
                 simple_float=123.4,
                 simple_true=True,
                 simple_false=False,
                 complex_1={'level0': 'value'},
                 complex_2={'string': 'value', 'level0': {'level1': 'value'}})


def test_parsing():
    """Verify that parsing an Event from JSON works."""
    path = os.path.dirname(__file__) + '/event.json'
    with open(path, encoding='utf-8', mode='rt') as f:
        event_json = json.load(f)
    event = Event.from_json(event_json)

    assert event.id == event_json['id']
    assert event.type == event_json['type']
    assert event.text == event_json['text']
    assert event.source == event_json['source']['id']
    assert event.time == event_json['time']
    assert event.creation_time == event_json['creationTime']

    assert isinstance(event.datetime, datetime)
    assert isinstance(event.creation_datetime, datetime)

    assert event['custom_attribute'] == 'value'
    assert event['custom_fragment.test.string'] == 'string'
    assert event['custom_fragment.test.false'] is False


def test_formatting(sample_event: Event):
    """Verify that JSON formatting works."""
    event_json = sample_event.to_json()

    # creation/server-side fields are not present in the JSON for a created object
    assert 'creationTime' not in event_json

    assert event_json['type'] == sample_event.type
    assert event_json['source']['id'] == sample_event.source
    assert event_json['text'] == sample_event.text
    assert event_json['time'] == sample_event.time

    assert event_json['simple_string'] == sample_event['simple_string']
    assert event_json['simple_int'] == sample_event['simple_int']
    assert event_json['simple_float'] == sample_event['simple_float']
    assert event_json['simple_true'] is True
    assert event_json['simple_false'] is False
    assert event_json['complex_1']['level0'] == 'value'
    assert event_json['complex_2']['level0']['level1'] == 'value'

    expected_keys = {'type', 'text', 'time', 'source',
                     'simple_string', 'simple_int', 'simple_float', 'simple_true', 'simple_false',
                     'complex_1', 'complex_2'}
    assert set(event_json.keys()) == expected_keys


def test_now_datetime():
    """Verify that 'now' is materialized to a timestring."""
    event = Event(type='type', time='now')

    assert event.time
    assert 'time' in event.to_json()
