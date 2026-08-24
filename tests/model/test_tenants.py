# Copyright (c) 2026 Christoph Souris

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyc8y.model.tenants import Tenant, Tenants

from tests.model.conftest import load_sample_file


@pytest.fixture
def tenants():
    return load_sample_file("tenants.json")


async def test_get_all(tenants):
    """Verify that Tenants.get_all returns parsed Tenant objects."""
    c8y = MagicMock()
    c8y.get = AsyncMock(side_effect=[tenants, {"tenants": []}])

    results = await Tenants(c8y).get_all()

    assert len(results) == 2
    assert all(isinstance(r, Tenant) for r in results)


async def test_select_params():
    """Verify that select parameters are forwarded to the HTTP call."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={"tenants": [], "statistics": {"totalPages": 1}})

    api = Tenants(c8y)
    _ = [r async for r in api.select(parent="P", domain="D", company="C", page_number=1)]

    params = dict(c8y.get.call_args.kwargs["params"])
    assert params["parent"] == "P"
    assert params["domain"] == "D"
    assert params["company"] == "C"


async def test_select_expression_overrides_filters():
    """Verify that expression overrides other filters."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={"tenants": [], "statistics": {"totalPages": 1}})

    api = Tenants(c8y)
    _ = [r async for r in api.select(expression="domain=D", domain="ignored", page_number=1)]

    call_url = c8y.get.call_args[0][0]
    assert "domain=D" in call_url
    # no params tuple when expression is used
    assert "params" not in c8y.get.call_args.kwargs


async def test_get_current(tenants):
    """Verify that Tenants.get_current returns a Tenant."""
    tenant_json = tenants["tenants"][0]

    c8y = MagicMock()
    c8y.get = AsyncMock(return_value=tenant_json)

    current = await Tenants(c8y).get_current()

    assert isinstance(current, Tenant)
    assert current.id == tenant_json["id"]
    c8y.get.assert_called_once_with("tenant/currentTenant")
