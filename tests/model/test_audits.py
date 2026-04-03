# Copyright (c) 2026 Christoph Souris

import json
import os
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyc8y.model.audit import AuditRecord, AuditRecords


FIXTURE_PATH = os.path.join(os.path.dirname(__file__), 'audit_records.json')


async def test_get_all():
    """Verify that AuditRecords.get_all returns parsed AuditRecord objects."""
    with open(FIXTURE_PATH, encoding='utf-8') as f:
        collection = json.load(f)

    c8y = MagicMock()
    c8y.get = AsyncMock(side_effect=[collection, {'auditRecords': []}])

    api = AuditRecords(c8y)
    results = await api.get_all()

    assert len(results) == 4
    assert all(isinstance(r, AuditRecord) for r in results)


async def test_select_params():
    """Verify that select parameters are forwarded to the HTTP call."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'auditRecords': [], 'statistics': {'totalPages': 1}})

    api = AuditRecords(c8y)
    _ = [r async for r in api.select(type='Alarm', source='123', user='u@example.com', page_number=1)]

    call_args = c8y.get.call_args
    params = dict(call_args[0][1])
    assert params['type'] == 'Alarm'
    assert params['source'] == '123'
    assert params['user'] == 'u@example.com'


async def test_select_by_application():
    """Verify that the application filter is forwarded."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'auditRecords': [], 'statistics': {'totalPages': 1}})

    api = AuditRecords(c8y)
    _ = [r async for r in api.select(application='myapp', page_number=1)]

    params = dict(c8y.get.call_args[0][1])
    assert params['application'] == 'myapp'


async def test_select_expression_overrides_filters():
    """Verify that expression overrides all other filters."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'auditRecords': [], 'statistics': {'totalPages': 1}})

    api = AuditRecords(c8y)
    _ = [r async for r in api.select(expression='type=Alarm', type='ignored', page_number=1)]

    call_url = c8y.get.call_args[0][0]
    assert 'type=Alarm' in call_url
    # with expression, no separate params tuple is passed
    assert len(c8y.get.call_args[0]) == 1


async def test_select_date_params():
    """Verify that date range parameters are forwarded."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'auditRecords': [], 'statistics': {'totalPages': 1}})

    api = AuditRecords(c8y)
    _ = [r async for r in api.select(date_from='2020-01-01', date_to='2021-01-01', page_number=1)]

    params = dict(c8y.get.call_args[0][1])
    assert 'dateFrom' in params
    assert 'dateTo' in params


async def test_select_min_max_age():
    """Verify that min/max age are converted to date params."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'auditRecords': [], 'statistics': {'totalPages': 1}})

    api = AuditRecords(c8y)
    _ = [r async for r in api.select(min_age=timedelta(days=3), max_age=timedelta(weeks=1), page_number=1)]

    params = dict(c8y.get.call_args[0][1])
    assert 'dateFrom' in params
    assert 'dateTo' in params
