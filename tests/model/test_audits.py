# Copyright (c) 2026 Christoph Souris

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyc8y.model.audit import AuditRecord, AuditRecords

from tests.model.conftest import load_sample_file


@pytest.fixture
def sample_json():
    return load_sample_file("audit_records.json")


async def test_get_all(sample_json):
    """Verify that AuditRecords.get_all returns parsed AuditRecord objects."""
    c8y = MagicMock()
    c8y.get = AsyncMock(side_effect=[sample_json, {"auditRecords": []}])

    results = await AuditRecords(c8y).get_all()

    assert len(results) == 4
    assert all(isinstance(r, AuditRecord) for r in results)


async def test_select_params():
    """Verify that select parameters are forwarded to the HTTP call."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={"auditRecords": [], "statistics": {"totalPages": 1}})

    api = AuditRecords(c8y)
    _ = [r async for r in api.select(type="Alarm", source="123", user="u@example.com", page_number=1)]

    params = dict(c8y.get.call_args.kwargs["params"])
    assert params["type"] == "Alarm"
    assert params["source"] == "123"
    assert params["user"] == "u@example.com"


async def test_select_by_application():
    """Verify that the application filter is forwarded."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={"auditRecords": [], "statistics": {"totalPages": 1}})

    api = AuditRecords(c8y)
    _ = [r async for r in api.select(application="myapp", page_number=1)]

    params = dict(c8y.get.call_args.kwargs["params"])
    assert params["application"] == "myapp"


async def test_select_expression_overrides_filters():
    """Verify that expression overrides all other filters."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={"auditRecords": [], "statistics": {"totalPages": 1}})

    api = AuditRecords(c8y)
    _ = [r async for r in api.select(expression="type=Alarm", type="ignored", page_number=1)]

    call_url = c8y.get.call_args.args[0]
    assert "type=Alarm" in call_url
    # no params tuple when expression is used
    assert "params" not in c8y.get.call_args.kwargs


async def test_select_date_params():
    """Verify that date range parameters are forwarded."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={"auditRecords": [], "statistics": {"totalPages": 1}})

    api = AuditRecords(c8y)
    _ = [r async for r in api.select(date_from="2020-01-01", date_to="2021-01-01", page_number=1)]

    params = dict(c8y.get.call_args.kwargs["params"])
    assert "dateFrom" in params
    assert "dateTo" in params


async def test_select_min_max_age():
    """Verify that min/max age are converted to date params."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={"auditRecords": [], "statistics": {"totalPages": 1}})

    api = AuditRecords(c8y)
    _ = [r async for r in api.select(min_age=timedelta(days=3), max_age=timedelta(weeks=1), page_number=1)]

    params = dict(c8y.get.call_args.kwargs["params"])
    assert "dateFrom" in params
    assert "dateTo" in params


async def test_get_count():
    """Verify that get_count returns totalPages and forwards filter params."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={"auditRecords": [], "statistics": {"totalPages": 7}})

    count = await AuditRecords(c8y).get_count(type="Alarm", source="123", user="u@example.com")

    assert count == 7
    params = dict(c8y.get.call_args.kwargs["params"])
    assert params["type"] == "Alarm"
    assert params["source"] == "123"
    assert params["user"] == "u@example.com"
    assert params["pageSize"] == "1"
    assert params["withTotalPages"] == "true"


async def test_get_count_expression():
    """Verify that an expression is passed directly and other filters are ignored."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={"auditRecords": [], "statistics": {"totalPages": 2}})

    count = await AuditRecords(c8y).get_count(expression="type=Alarm", type="ignored")

    assert count == 2
    call_url = c8y.get.call_args.args[0]
    assert "type=Alarm" in call_url
    # no params tuple when expression is used
    assert "params" not in c8y.get.call_args.kwargs


async def test_get_count_application_filter():
    """Verify that the application filter is forwarded."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={"auditRecords": [], "statistics": {"totalPages": 5}})

    count = await AuditRecords(c8y).get_count(application="myapp")

    assert count == 5
    params = dict(c8y.get.call_args.kwargs["params"])
    assert params["application"] == "myapp"
