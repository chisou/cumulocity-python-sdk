# Copyright (c) 2026 Christoph Souris

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyc8y.model.operation import BulkOperation, BulkOperations, BulkStatus, GeneralBulkStatus

from tests.model.conftest import load_sample_file


SAMPLES_JSON = load_sample_file("bulk_operations.json")


@pytest.mark.parametrize('sample_json', SAMPLES_JSON['bulkOperations'])
def test_parsing(sample_json):
    """Verify that parsing a BulkOperation from JSON works."""
    op = BulkOperation.from_json(sample_json)

    assert op.id == sample_json['id']
    assert op.creation_ramp == sample_json['creationRamp']
    assert op.status == sample_json['status']
    assert op.general_status == sample_json['generalStatus']
    assert op.start_time == sample_json['startDate']
    assert op.operation_prototype['description'] == sample_json['operationPrototype']['description']

    if 'groupId' in sample_json:
        assert op.group_id == sample_json['groupId']
    if 'failedParentId' in sample_json:
        assert op.failed_parent_id == sample_json['failedParentId']


def test_formatting():
    """Verify that JSON formatting works for a BulkOperation."""
    op = BulkOperation(
        group_id='group-id',
        failed_parent_id='failed-parent-id',
        start_time='now',
        creation_ramp=123,
        operation_prototype={
            'description': 'some description',
            'c8y_Firmware': {
                'name': 'MyFirmware',
                'url': 'http://example.com',
                'version': '1.0.0',
            },
        },
        note='custom note',
    )

    op_json = op.json

    assert op_json['groupId'] == op.group_id
    assert op_json['failedParentId'] == op.failed_parent_id
    assert op_json['creationRamp'] == op.creation_ramp
    assert op_json['operationPrototype']['description'] == 'some description'
    assert op_json['note'] == op['note']


def test_status_constants():
    """Verify BulkOperation status and general status constants."""
    assert BulkStatus.ACTIVE == 'ACTIVE'
    assert BulkStatus.COMPLETED == 'COMPLETED'
    assert BulkStatus.IN_PROGRESS == 'IN_PROGRESS'

    assert GeneralBulkStatus.EXECUTING == 'EXECUTING'
    assert GeneralBulkStatus.SUCCESSFUL == 'SUCCESSFUL'
    assert GeneralBulkStatus.FAILED == 'FAILED'


async def test_get_all():
    """Verify BulkOperations.get_all returns parsed BulkOperation objects."""
    c8y = MagicMock()
    c8y.get = AsyncMock(side_effect=[SAMPLES_JSON, {'bulkOperations': []}])

    results = await BulkOperations(c8y).get_all()

    assert len(results) == 2
    assert all(isinstance(r, BulkOperation) for r in results)
    assert results[0].id == SAMPLES_JSON['bulkOperations'][0]['id']
