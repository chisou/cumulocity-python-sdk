# Copyright (c) 2026 Christoph Souris

from datetime import datetime

import pytest

from pyc8y.model.operation import Operation, OperationStatus

from tests.model.conftest import load_sample_file


@pytest.fixture
def operation_json():
    return load_sample_file("operation.json")


def test_parsing(operation_json):
    """Verify that parsing an Operation from JSON works."""
    op = Operation.from_json(operation_json)

    assert op.id == operation_json['id']
    assert op.device_id == operation_json['deviceId']
    assert op.status == operation_json['status']
    assert op.description == operation_json['description']
    assert op.creation_time == operation_json['creationTime']

    assert isinstance(op.creation_datetime, datetime)

    assert op['c8y_Command']['text'] == operation_json['c8y_Command']['text']


@pytest.fixture
def sample_operation():
    """Provide a sample Operation for various tests."""
    return Operation(
        device_id='12345',
        status=OperationStatus.FAILED,
        description='description text',
        simple_string='string',
        simple_int=123,
        simple_float=123.4,
        simple_true=True,
        simple_false=False,
        complex_1={'level0': 'value'},
        complex_2={'string': 'value', 'level0': {'level1': 'value'}},
    )


def test_formatting(sample_operation):
    """Verify that JSON formatting works."""
    op_json = sample_operation.to_json()

    assert 'creationTime' not in op_json

    assert op_json['deviceId'] == sample_operation.device_id
    assert op_json['description'] == sample_operation.description
    assert op_json['status'] == sample_operation.status

    assert op_json['simple_string'] == 'string'
    assert op_json['simple_int'] == 123
    assert op_json['simple_float'] == 123.4
    assert op_json['simple_true'] is True
    assert op_json['simple_false'] is False
    assert op_json['complex_1']['level0'] == 'value'
    assert op_json['complex_2']['level0']['level1'] == 'value'

    expected_keys = {'deviceId', 'status', 'description',
                     'simple_string', 'simple_int', 'simple_float', 'simple_true', 'simple_false',
                     'complex_1', 'complex_2'}
    assert set(op_json.keys()) == expected_keys
