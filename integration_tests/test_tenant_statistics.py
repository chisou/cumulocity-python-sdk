# Copyright (c) 2026 Christoph Souris

import datetime as dt
import os
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import pytest

from pyc8y.client import CumulocityClient
from pyc8y.model.tenant_statistics import (
    TenantStatistics,
    DeviceStatistics,
    UsageStatistics,
    TenantStatisticsFile,
)
from pyc8y.rest import AccessDeniedError


@pytest.fixture(scope="module")
def statistics(live_c8y: CumulocityClient) -> TenantStatistics:
    return TenantStatistics(live_c8y)


@pytest.fixture(scope="module")
def tenant_id(live_c8y: CumulocityClient) -> str:
    return live_c8y.tenant_id


async def test_select_usage_statistics(statistics: TenantStatistics):
    """Verify that usage statistics can be iterated."""
    results = [x async for x in statistics.select_usage_statistics(limit=3)]
    assert all(isinstance(x, UsageStatistics) for x in results)


async def test_get_all_usage_statistics(statistics: TenantStatistics):
    """Verify that usage statistics can be retrieved as a list."""
    results = await statistics.get_all_usage_statistics(limit=3)
    assert isinstance(results, list)
    assert all(isinstance(x, UsageStatistics) for x in results)


async def test_get_usage_summary(statistics: TenantStatistics, tenant_id: str):
    """Verify that the usage summary endpoint returns a result."""
    result = await statistics.get_usage_summary(tenant_id)
    assert isinstance(result, UsageStatistics)


async def test_get_usage_summary_all_tenants(statistics: TenantStatistics):
    """Verify that the all-tenants usage summary endpoint returns a result."""
    result = await statistics.get_usage_summary_all_tenants()
    assert isinstance(result, UsageStatistics)


async def test_select_daily_device_statistics(statistics: TenantStatistics, tenant_id: str):
    """Verify that daily device statistics can be iterated."""
    today = dt.datetime.now(dt.timezone.utc)
    results = [x async for x in statistics.select_daily_device_statistics(tenant_id, today, limit=3)]
    assert all(isinstance(x, DeviceStatistics) for x in results)


async def test_get_all_daily_device_statistics(statistics: TenantStatistics, tenant_id: str):
    """Verify that daily device statistics can be retrieved as a list."""
    today = dt.datetime.now(dt.timezone.utc)
    results = await statistics.get_all_daily_device_statistics(tenant_id, today, limit=3)
    assert isinstance(results, list)
    assert all(isinstance(x, DeviceStatistics) for x in results)


async def test_select_monthly_device_statistics(statistics: TenantStatistics, tenant_id: str):
    """Verify that monthly device statistics can be iterated."""
    today = dt.datetime.now(dt.timezone.utc)
    results = [x async for x in statistics.select_monthly_device_statistics(tenant_id, today, limit=3)]
    assert all(isinstance(x, DeviceStatistics) for x in results)


async def test_get_all_monthly_device_statistics(statistics: TenantStatistics, tenant_id: str):
    """Verify that monthly device statistics can be retrieved as a list."""
    today = dt.datetime.now(dt.timezone.utc)
    results = await statistics.get_all_monthly_device_statistics(tenant_id, today, limit=3)
    assert isinstance(results, list)
    assert all(isinstance(x, DeviceStatistics) for x in results)


async def test_files(live_c8y: CumulocityClient, tenant_id: str):
    """Verify that statistics files can be created, iterated and downloaded."""
    date_from = "2025-01-01"
    date_to = "2025-01-02"

    try:
        # (1) create individual files
        file1 = await TenantStatisticsFile(c8y=live_c8y, date_from=date_from, date_to=date_to).create()
        file2 = TenantStatisticsFile(c8y=live_c8y, date_from=date_from, date_to=date_to)
        await live_c8y.tenant_statistics.generate(file2)
        await live_c8y.tenant_statistics.generate(date_from=date_from, date_to=date_to)
        # -> can be downloaded
        assert await file1.read()

        # (2) select multiple files
        results = await live_c8y.tenant_statistics.get_all_files(date_from=date_from, date_to=date_to, limit=3)
        # -> there should be at least our files
        assert len(results) == 3
        # -> they can be downloaded
        file_id = results[0].id
        file_bytes, file_name = await live_c8y.tenant_statistics.get_file(file_id)
        # assert file_bytes == (awai[0]
        with TemporaryDirectory() as tmpdir:
            fn = os.path.join(tmpdir, file_name)
            with open(fn, "wb") as f:
                f.write(file_bytes)
            # -> should be a zip file
            with ZipFile(fn, "r") as zf:
                assert zf.namelist()
    except AccessDeniedError:
        pytest.skip("Test needs a management tenant and tenant admin role.")
