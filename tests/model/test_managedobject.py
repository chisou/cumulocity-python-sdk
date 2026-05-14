# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris
# pylint: disable=redefined-outer-name, protected-access

import datetime
import json
import os

import pytest

from pyc8y.model.managed_object import Availability, Device, DeviceGroup, ManagedObject


def test_parsing():
    """Verify that parsing a ManagedObject from JSON works."""

    # 1) read a sample object from file
    path = os.path.dirname(__file__) + '/managed_object.json'
    with open(path, encoding='utf-8', mode='rt') as f:
        object_json = json.load(f)

    mo = ManagedObject.from_json(object_json)

    # 2) assert parsed data
    assert mo.id == object_json['id']
    assert mo.type == object_json['type']
    assert mo.name == object_json['name']

    # 3) custom fragments accessible via item syntax
    assert mo['applicationId'] == object_json['applicationId']
    test_json = object_json['c8y_Status']['details']['test']
    assert mo['c8y_Status.details.test.string'] == test_json['string']
    assert mo['c8y_Status.details.test.int'] == test_json['int']
    assert mo['c8y_Status.details.test.float'] == test_json['float']
    assert mo['c8y_Status.details.test.true'] == test_json['true']
    assert mo['c8y_Status.details.test.false'] == test_json['false']


def test_parsing_availability():
    """Verify that parsing of an Availability object works as expected."""
    path = os.path.dirname(__file__) + '/availability.json'
    with open(path, encoding='utf-8', mode='rt') as f:
        availability_json = json.load(f)
    availability = Availability(availability_json)

    assert availability.connection_status == Availability.ConnectionStatus.DISCONNECTED
    assert availability.data_status == Availability.DataStatus.AVAILABLE
    assert availability.interval_minutes == 50
    assert availability.device_id == '12345'
    assert availability.external_id == 'esn12345'
    assert availability.last_message_datetime == datetime.datetime.fromisoformat('2020-01-31 11:22:33.456+00:00')


@pytest.fixture(scope='function')
def sample_object() -> ManagedObject:
    """Provide a sample object for various tests."""
    return ManagedObject(name='name', type='type', owner='owner',
                         simple_string='string',
                         simple_int=123,
                         simple_float=123.4,
                         simple_true=True,
                         simple_false=False,
                         complex_1={'level0': 'value'},
                         complex_2={'string': 'value', 'level0': {'level1': 'value'}})


def test_formatting(sample_object: ManagedObject):
    """Verify that JSON formatting works."""
    object_json = sample_object.to_json()

    assert object_json['name'] == sample_object.name
    assert object_json['type'] == sample_object.type
    assert object_json['owner'] == sample_object.owner

    assert object_json['simple_string'] == sample_object['simple_string']
    assert object_json['simple_int'] == sample_object['simple_int']
    assert object_json['simple_float'] == sample_object['simple_float']
    assert object_json['simple_true'] is True
    assert object_json['simple_false'] is False
    assert object_json['complex_1']['level0'] == 'value'
    assert object_json['complex_2']['level0']['level1'] == 'value'

    expected_keys = {'name', 'type', 'owner',
                     'simple_string', 'simple_int', 'simple_float', 'simple_true', 'simple_false',
                     'complex_1', 'complex_2'}
    assert set(object_json.keys()) == expected_keys


@pytest.fixture(scope='session')
def object_with_fragments():
    """Create an object featuring various custom fragments."""

    kwargs = {'simple_string': 'string',
              'simple_int': 123,
              'simple_float': 123.4,
              'simple_true': True,
              'simple_false': False,
              'complex_1': {'level0': 'value'},
              'complex_2': {'level0': {'level1': 'value'}}}
    return kwargs, ManagedObject(**kwargs)


def test_fragment_presence(object_with_fragments):
    """Verify that fragment presence can be checked."""

    kwargs, mo = object_with_fragments

    for attr_name in kwargs.keys():
        assert attr_name in mo
        assert mo.has(attr_name)
    assert 'wrong_one' not in mo
    assert not mo.has('wrong_again')


def test_item_access(object_with_fragments):
    """Verify that fragments can be accessed using [] operator."""

    kwargs, mo = object_with_fragments

    assert mo['simple_string'] == kwargs['simple_string']
    assert mo['simple_int'] == kwargs['simple_int']
    assert mo['simple_float'] == kwargs['simple_float']
    assert mo['simple_true'] == kwargs['simple_true']
    assert mo['simple_false'] == kwargs['simple_false']

    assert mo['complex_1.level0'] == kwargs['complex_1']['level0']
    assert mo['complex_2.level0.level1'] == kwargs['complex_2']['level0']['level1']

    # accessing a missing path raises
    with pytest.raises(KeyError):
        _ = mo['not_existing']


@pytest.mark.parametrize('obj, expected_repr', [
    (ManagedObject(), "ManagedObject()"),
    (ManagedObject(name='NAME', type='TYPE'), "ManagedObject(type=TYPE)"),
    (Device(), "Device()"),
    (Device(name='NAME', type='TYPE'), "Device(type=TYPE)"),
    (DeviceGroup(), "DeviceGroup(type=c8y_DeviceSubGroup)"),
    (DeviceGroup(root=True), "DeviceGroup(type=c8y_DeviceGroup)"),
    (ManagedObject.from_json({'id': 12, 'name': 'NAME', 'type': 'TYPE', 'other': 'OTHER'}),
     "ManagedObject(id=12, type=TYPE)"),
    (Device.from_json({'id': 12, 'name': 'NAME', 'type': 'TYPE', 'other': 'OTHER', 'c8y_IsDevice': {}}),
     "Device(id=12, type=TYPE)"),
])
def test_repr(obj, expected_repr):
    """Verify that the string representation works as expected."""
    assert str(obj) == expected_repr
