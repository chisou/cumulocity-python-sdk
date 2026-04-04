# Copyright (c) 2026 Christoph Souris

import asyncio

from pyc8y.client import CumulocityClient
from pyc8y.model.managed_object import Device
from pyc8y.model.operation import Operation, OperationStatus

from util.testing_util import RandomNameGenerator


async def test_CRUD(live_c8y: CumulocityClient, session_device: Device):  # noqa (case)
    """Verify that basic creation, lookup and update of Operations works as expected."""

    name = RandomNameGenerator.random_name()

    # (1) create operation
    operation = await Operation(
        live_c8y,
        device_id=session_device.id,
        description=f'Description {name}',
        c8y_Command={'text': 'Command text'},
    ).create()

    # -> operation should have been created and in PENDING state
    operations = await live_c8y.operations.get_all(device_id=session_device.id, status=OperationStatus.PENDING)
    assert len(operations) == 1
    assert operations[0].id == operation.id

    # -> same result with get_last
    operation2 = await live_c8y.operations.get_last(device_id=session_device.id, status=OperationStatus.PENDING)
    assert operation2.id == operation.id

    # (2) update operation
    operation.status = OperationStatus.EXECUTING
    operation.description = 'New description'
    operation['c8y_Command'] = {'text': 'Updated command text'}
    operation['c8y_CustomCommand'] = {'value': 'good'}
    await operation.update()

    # -> all fields have been updated in Cumulocity
    operation2 = await live_c8y.operations.get(operation.id)
    assert operation2.status == operation.status
    assert operation2.description == operation.description
    assert operation2['c8y_Command.text'] == operation['c8y_Command.text']
    assert operation2['c8y_CustomCommand.value'] == operation['c8y_CustomCommand.value']

    # (3) delete operation
    await live_c8y.operations.delete_by(device_id=session_device.id)

    # -> cannot be found anymore
    assert not await live_c8y.operations.get_all(device_id=session_device.id)


async def test_get(live_c8y: CumulocityClient, session_device: Device):
    """Verify that query-like retrieval works as expected."""

    # (1) create operations
    operations = list(await asyncio.gather(*[
        Operation(
            live_c8y,
            device_id=session_device.id,
            description=f'Description {i}',
            c8y_Command={'text': 'Command text'},
        ).create()
        for i in range(5)
    ]))

    try:
        # (2) all should have been created and in PENDING state
        result = await live_c8y.operations.get_all(device_id=session_device.id, status=OperationStatus.PENDING)
        assert len(result) == 5
        assert all(o.device_id == session_device.id for o in result)

        # (3) get last
        result = await live_c8y.operations.get_last(device_id=session_device.id)
        assert isinstance(result, Operation)
        assert result.device_id == session_device.id

        # (4) retrieving subsets
        operations[0].status = OperationStatus.EXECUTING
        operations[1].status = OperationStatus.EXECUTING
        await asyncio.gather(operations[0].update(), operations[1].update())

        result = await live_c8y.operations.get_all(device_id=session_device.id, status=OperationStatus.PENDING)
        assert len(result) == 3
        result = await live_c8y.operations.get_last(device_id=session_device.id, status=OperationStatus.PENDING)
        assert result.status == OperationStatus.PENDING
        assert result.device_id == session_device.id

        result = await live_c8y.operations.get_all(device_id=session_device.id, status=OperationStatus.EXECUTING)
        assert len(result) == 2
        result = await live_c8y.operations.get_last(device_id=session_device.id, status=OperationStatus.EXECUTING)
        assert result.status == OperationStatus.EXECUTING
        assert result.device_id == session_device.id

        # (5) deleting subsets
        await live_c8y.operations.delete_by(device_id=session_device.id, status=OperationStatus.EXECUTING)
        assert await live_c8y.operations.get_all(device_id=session_device.id, status=OperationStatus.EXECUTING) == []
        assert len(await live_c8y.operations.get_all(device_id=session_device.id, status=OperationStatus.PENDING)) == 3

        # (6) no match with get_last
        assert await live_c8y.operations.get_last(device_id=session_device.id, status=OperationStatus.EXECUTING) is None

    finally:
        await live_c8y.operations.delete_by(device_id=session_device.id)
