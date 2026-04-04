# Copyright (c) 2026 Christoph Souris

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyc8y.model.operation import Operation, Operations, OperationStatus

from tests.model.conftest import load_sample_file


@pytest.fixture
def operation_json():
    return load_sample_file("operation.json")


async def test_get_all(operation_json):
    """Verify that Operations.get_all returns parsed Operation objects."""
    c8y = MagicMock()
    c8y.get = AsyncMock(side_effect=[
        {'operations': [operation_json], 'statistics': {}},
        {'operations': []},
    ])

    results = await Operations(c8y).get_all()

    assert len(results) == 1
    assert isinstance(results[0], Operation)
    assert results[0].id == operation_json['id']


async def test_select_params():
    """Verify that select parameters are forwarded to the HTTP call."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'operations': [], 'statistics': {'totalPages': 1}})

    api = Operations(c8y)
    _ = [r async for r in api.select(
        agent_id='A', device_id='D', bulk_id='B',
        status=OperationStatus.PENDING,
        page_number=1,
    )]

    params = dict(c8y.get.call_args[0][1])
    assert params['agentId'] == 'A'
    assert params['deviceId'] == 'D'
    assert params['bulkOperationId'] == 'B'
    assert params['status'] == 'PENDING'


async def test_select_fragment_param():
    """Verify that the fragment param maps to fragmentType."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'operations': [], 'statistics': {'totalPages': 1}})

    api = Operations(c8y)
    _ = [r async for r in api.select(fragment='c8y_Command', page_number=1)]

    params = dict(c8y.get.call_args[0][1])
    assert params['fragmentType'] == 'c8y_Command'
    assert 'fragment' not in params


async def test_select_expression_overrides_filters():
    """Verify that expression overrides all other filters."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'operations': [], 'statistics': {'totalPages': 1}})

    api = Operations(c8y)
    _ = [r async for r in api.select(expression='status=PENDING', device_id='ignored', page_number=1)]

    call_url = c8y.get.call_args[0][0]
    assert 'status=PENDING' in call_url
    assert len(c8y.get.call_args[0]) == 1


async def test_select_date_params():
    """Verify that date parameters are forwarded."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'operations': [], 'statistics': {'totalPages': 1}})

    api = Operations(c8y)
    _ = [r async for r in api.select(date_to='2021-12-31', page_number=1)]

    params = dict(c8y.get.call_args[0][1])
    assert 'dateTo' in params


async def test_select_min_max_age():
    """Verify that min/max age are converted to date params."""
    from datetime import timedelta
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'operations': [], 'statistics': {'totalPages': 1}})

    api = Operations(c8y)
    _ = [r async for r in api.select(min_age=timedelta(days=3), max_age=timedelta(weeks=1), page_number=1)]

    params = dict(c8y.get.call_args[0][1])
    assert 'dateFrom' in params
    assert 'dateTo' in params


async def test_delete_by_params():
    """Verify that delete_by forwards parameters to the HTTP delete call."""
    c8y = MagicMock()
    c8y.delete = AsyncMock()

    api = Operations(c8y)
    await api.delete_by(device_id='D', status=OperationStatus.FAILED)

    params = dict(c8y.delete.call_args[1]['params'])
    assert params['deviceId'] == 'D'
    assert params['status'] == 'FAILED'


async def test_get_last(operation_json):
    """Verify that get_last returns a single Operation or None."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'operations': [operation_json], 'statistics': {'totalPages': 1}})

    result = await Operations(c8y).get_last(device_id='123456')

    assert isinstance(result, Operation)
    assert result.id == operation_json['id']
