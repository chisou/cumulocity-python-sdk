# Copyright (c) 2026 Christoph Souris

import asyncio

from pyc8y.client import CumulocityClient
from pyc8y.model.managed_object import Device, DeviceGroup
from pyc8y.model.matcher import field
from pyc8y.model.operation import BulkOperation, Operation, BulkStatus, GeneralBulkStatus, OperationStatus


async def test_CRU(live_c8y: CumulocityClient, session_device: Device):  # noqa (case)
    """Verify that basic creation, lookup and update of Bulk Operations works as expected."""

    # (1) Create a device group for the sample device
    group: DeviceGroup = await DeviceGroup(live_c8y, root=True, name=session_device.name + '_Group').create()
    await group.add_child_asset(session_device)

    try:
        # (2) create bulk operation
        bulk: BulkOperation = await BulkOperation(
            live_c8y,
            group_id=group.id,
            start_time='now',
            creation_ramp=1,
            operation_prototype={
                'description': f"Update firmware for device group '{group.name}'.",
                'c8y_FirmWare': {'version': '1.0.0'},
            },
        ).create()

        # wait for the bulk operation to be processed
        await asyncio.sleep(5)

        # check if bulk operation was created
        all_ids = [x.id for x in await live_c8y.bulk_operations.get_all()]
        assert bulk.id in all_ids

        # use client-side filtering
        assert bulk.id in [
            x.id for x in await live_c8y.bulk_operations.get_all(include=field("groupId", group.id))
        ]

        # check count
        assert len(all_ids) == await live_c8y.bulk_operations.get_count()

        # (3) initially the status should be EXECUTING/COMPLETED as all
        #     child operations should have been created but not completed
        bulk = await live_c8y.bulk_operations.get(bulk.id)
        assert bulk.general_status == GeneralBulkStatus.EXECUTING
        assert bulk.status == BulkStatus.COMPLETED
        assert bulk['progress']['all'] == 1
        assert bulk['progress']['pending'] == 1

        # (4) find child operations
        op = (await live_c8y.operations.get_all(bulk_id=bulk.id))[0]
        assert op.status == OperationStatus.PENDING

        # (5) fail child operation
        op.status = OperationStatus.FAILED
        await op.update()

        # (6) bulk operation should now reflect the failure
        bulk = await live_c8y.bulk_operations.get(bulk.id)
        assert bulk.general_status in [
            GeneralBulkStatus.COMPLETED_WITH_FAILURES,
            GeneralBulkStatus.FAILED,
        ]
        assert bulk['progress']['all'] == 1
        assert bulk['progress']['failed'] == 1
        assert await live_c8y.operations.get_count(bulk_id=bulk.id) == 1

    finally:
        # bulk operations cannot be deleted physically
        await group.delete()
