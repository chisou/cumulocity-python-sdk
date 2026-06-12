# Copyright (c) 2026 Christoph Souris

import datetime as dt
from typing import Sequence, AsyncIterator, Self

from pyc8y.model.model_base import (
    JsonObject,
    json_property,
    CumulocityResource,
    map_params,
    datetime_property,
    CumulocityObject,
    WithId,
    resolve_page_size,
    time_property,
)
from pyc8y.model.model_util import coerce_timestring
from pyc8y.rest import CumulocityRestClient, FileDownload
from pyc8y.types import (
    TenantDeviceStatisticsMeta,
    TenantUsageStatisticsMeta,
    TenantStatisticsFilesMeta,
)


class DeviceStatistics(JsonObject):
    """Device-level statistics for a single day or month."""


class UsageStatistics(JsonObject):
    """Tenant-level usage statistics for a period."""


class _DailyDeviceStatistics(CumulocityResource):
    """Internal resource for /tenant/statistics/device/{tenantId}/daily/{date}."""

    _meta = TenantDeviceStatisticsMeta
    _object_type = DeviceStatistics

    def select(
            self,
            tenant_id: str,
            date: str | dt.datetime,
            *,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
    ) -> AsyncIterator[DeviceStatistics]:
        page_size = resolve_page_size(page_size, limit)
        date_str = coerce_timestring(date)
        resource = f"tenant/statistics/device/{tenant_id}/daily/{date_str}"

        async def fetch_page(page: int, expression, params, **_) -> list:
            result = await self.c8y.get(resource, params=(("currentPage", str(page)),
                                                          ("pageSize", str(page_size or 5))))
            return result[self._meta.collection_name]

        return self._iterate(
            fetch_page=fetch_page,
            page_number=page_number,
            limit=limit,
            as_values=as_values,
            workers=workers,
            preserve_order=False,
        )



class _MonthlyDeviceStatistics(CumulocityResource):
    """Internal resource for /tenant/statistics/device/{tenantId}/monthly/{date}."""

    _meta = TenantDeviceStatisticsMeta
    _object_type = DeviceStatistics

    def select(
            self,
            tenant_id: str,
            date: str | dt.datetime,
            *,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
    ) -> AsyncIterator[DeviceStatistics]:
        page_size = resolve_page_size(page_size, limit)
        date_str = coerce_timestring(date)
        resource = f"tenant/statistics/device/{tenant_id}/monthly/{date_str}"

        async def fetch_page(page: int, expression, params, **_) -> list:
            result = await self.c8y.get(resource, params=(("currentPage", str(page)),
                                                          ("pageSize", str(page_size or 5))))
            return result[self._meta.collection_name]

        return self._iterate(
            fetch_page=fetch_page,
            page_number=page_number,
            limit=limit,
            as_values=as_values,
            workers=workers,
            preserve_order=False,
        )



class _UsageStatistics(CumulocityResource):
    """Internal resource for /tenant/statistics."""

    _meta = TenantUsageStatisticsMeta
    _object_type = UsageStatistics

    def select(
            self,
            expression: str | None = None,
            *,
            before: str | dt.datetime | None = None,
            after: str | dt.datetime | None = None,
            date_from: str | dt.datetime | None = None,
            date_to: str | dt.datetime | None = None,
            min_age: str | dt.timedelta | None = None,
            max_age: str | dt.timedelta | None = None,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
            **kwargs,
    ) -> AsyncIterator[UsageStatistics]:
        page_size = resolve_page_size(page_size, limit)
        params = (
            map_params(
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                page_size=page_size,
                **kwargs,
            )
            if not expression
            else ()
        )
        return self._iterate(
            expression=expression,
            params=params,
            page_number=page_number,
            limit=limit,
            as_values=as_values,
            workers=workers,
            preserve_order=False,
        )



class TenantStatisticsFile(WithId, CumulocityObject):

    _meta = TenantStatisticsFilesMeta

    id = json_property("id", read_only=True)
    instance = json_property("instanceName", read_only=True)
    generation_date = json_property("generationDate", read_only=True)
    generation_datetime = datetime_property("generationDate")
    date_from = time_property("dateFrom")
    date_to = time_property("dateTo")
    datetime_from = datetime_property("dateFrom")
    datetime_to = datetime_property("dateTo")

    def __init__(
            self,
            c8y: CumulocityRestClient | None = None,
            *,
            date_from: str | dt.date | dt.datetime | None = None,
            date_to: str | dt.date | dt.datetime | None = None,
    ):
        super().__init__(c8y)
        self.date_from = date_from
        self.date_to = date_to

    async def generate(self) -> Self:
        return await self._create()

    async def read(self) -> FileDownload:
        self._assert_c8y()
        self._assert_key()
        return await self.c8y.get_file(self.object_path)

    async def create(self) -> Self:
        return await self.generate()


class _StatisticsFiles(CumulocityResource):
    """Internal resource for /tenant/statistics/files."""

    _meta = TenantStatisticsFilesMeta
    _object_type = TenantStatisticsFile

    def select(
            self,
            expression: str | None = None,
            *,
            before: str | dt.datetime | None = None,
            after: str | dt.datetime | None = None,
            date_from: str | dt.datetime | None = None,
            date_to: str | dt.datetime | None = None,
            min_age: str | dt.timedelta | None = None,
            max_age: str | dt.timedelta | None = None,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
            **kwargs,
    ) -> AsyncIterator[TenantStatisticsFile]:
        page_size = resolve_page_size(page_size, limit)
        params = (
            map_params(
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                page_size=page_size,
                **kwargs,
            )
            if not expression
            else ()
        )
        return self._iterate(
            expression=expression,
            params=params,
            page_number=page_number,
            limit=limit,
            as_values=as_values,
            workers=workers,
            preserve_order=False,
        )

    async def generate(
            self,
            *files: TenantStatisticsFile,
            date_from: str | dt.date | dt.datetime | None = None,
            date_to: str | dt.date | dt.datetime | None = None,
            workers: int | None = None,
    ):
        if files:
            await self._create(*files, workers=workers)
        else:
            await TenantStatisticsFile(self.c8y, date_from=date_from, date_to=date_to).generate()

    async def create(
            self,
            *files: TenantStatisticsFile,
            date_from: str | dt.date | dt.datetime | None = None,
            date_to: str | dt.date | dt.datetime | None = None,
            workers: int | None = None,
    ):
        return await self.generate(
            *files,
            date_from=date_from,
            date_to=date_to,
            workers=workers,
        )

    async def get(self, file_id: str) -> FileDownload:
        return await self.c8y.get_file(self.build_object_path(file_id))

    async def get_latest(self, *, month: str | dt.datetime = "today") -> FileDownload:
        month_string = coerce_timestring(month)
        return await self.c8y.get_file(f"/tenant/statistics/files/latest/{month_string}")


class TenantStatistics:
    """Provides access to the Tenant Statistics API.

    Covers device-level statistics (daily/monthly per tenant), tenant-level
    usage statistics, and statistics file management.
    """

    def __init__(self, c8y: CumulocityRestClient):
        self.c8y = c8y
        self._daily = _DailyDeviceStatistics(c8y)
        self._monthly = _MonthlyDeviceStatistics(c8y)
        self._usage = _UsageStatistics(c8y)
        self._files = _StatisticsFiles(c8y)

    # --- device statistics ---

    def select_daily_device_statistics(
            self,
            tenant_id: str,
            date: str | dt.datetime,
            *,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
    ) -> AsyncIterator[DeviceStatistics]:
        return self._daily.select(tenant_id, date, limit=limit, page_size=page_size,
                                  page_number=page_number, as_values=as_values, workers=workers)

    async def get_all_daily_device_statistics(
            self,
            tenant_id: str,
            date: str | dt.datetime,
            *,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
    ) -> list[DeviceStatistics]:
        return [x async for x in self._daily.select(tenant_id, date, limit=limit, page_size=page_size,
                                                     page_number=page_number, as_values=as_values, workers=workers)]

    def select_monthly_device_statistics(
            self,
            tenant_id: str,
            date: str | dt.datetime,
            *,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
    ) -> AsyncIterator[DeviceStatistics]:
        return self._monthly.select(tenant_id, date, limit=limit, page_size=page_size,
                                    page_number=page_number, as_values=as_values, workers=workers)

    async def get_all_monthly_device_statistics(
            self,
            tenant_id: str,
            date: str | dt.datetime,
            *,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
    ) -> list[DeviceStatistics]:
        return [x async for x in self._monthly.select(tenant_id, date, limit=limit, page_size=page_size,
                                                       page_number=page_number, as_values=as_values, workers=workers)]

    # --- usage statistics ---

    def select_usage_statistics(
            self,
            expression: str | None = None,
            *,
            before: str | dt.datetime | None = None,
            after: str | dt.datetime | None = None,
            date_from: str | dt.datetime | None = None,
            date_to: str | dt.datetime | None = None,
            min_age: str | dt.timedelta | None = None,
            max_age: str | dt.timedelta | None = None,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
            **kwargs,
    ) -> AsyncIterator[UsageStatistics]:
        return self._usage.select(expression, before=before, after=after, date_from=date_from,
                                  date_to=date_to, min_age=min_age, max_age=max_age, limit=limit,
                                  page_size=page_size, page_number=page_number, as_values=as_values,
                                  workers=workers, **kwargs)

    async def get_all_usage_statistics(
            self,
            expression: str | None = None,
            *,
            before: str | dt.datetime | None = None,
            after: str | dt.datetime | None = None,
            date_from: str | dt.datetime | None = None,
            date_to: str | dt.datetime | None = None,
            min_age: str | dt.timedelta | None = None,
            max_age: str | dt.timedelta | None = None,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
            **kwargs,
    ) -> list[UsageStatistics]:
        return [
            x
            async for x in self._usage.select(
                expression,
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
                **kwargs
            )
        ]

    async def get_usage_summary(
            self,
            tenant_id: str | None = None,
            *,
            before: str | dt.datetime | None = None,
            after: str | dt.datetime | None = None,
            date_from: str | dt.datetime | None = None,
            date_to: str | dt.datetime | None = None,
            min_age: str | dt.timedelta | None = None,
            max_age: str | dt.timedelta | None = None,
    ) -> UsageStatistics:
        params = map_params(
            before=before,
            after=after,
            date_from=date_from,
            date_to=date_to,
            min_age=min_age,
            max_age=max_age,
            **({"tenant_id": tenant_id} if tenant_id else {}),
        )
        return UsageStatistics(await self.c8y.get("tenant/statistics/summary", params=params))

    async def get_usage_summary_all_tenants(
            self,
            *,
            before: str | dt.datetime | None = None,
            after: str | dt.datetime | None = None,
            date_from: str | dt.datetime | None = None,
            date_to: str | dt.datetime | None = None,
            min_age: str | dt.timedelta | None = None,
            max_age: str | dt.timedelta | None = None,
    ) -> UsageStatistics:
        params = map_params(
            before=before,
            after=after,
            date_from=date_from,
            date_to=date_to,
            min_age=min_age,
            max_age=max_age,
        )
        return UsageStatistics(await self.c8y.get("tenant/statistics/allTenantsSummary", params=params))

    # --- statistics files ---

    def select_files(
            self,
            expression: str | None = None,
            *,
            before: str | dt.datetime | None = None,
            after: str | dt.datetime | None = None,
            date_from: str | dt.datetime | None = None,
            date_to: str | dt.datetime | None = None,
            min_age: str | dt.timedelta | None = None,
            max_age: str | dt.timedelta | None = None,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
            **kwargs,
    ) -> AsyncIterator[TenantStatisticsFile]:
        return self._files.select(
            expression,
            before=before,
            after=after,
            date_from=date_from,
            date_to=date_to,
            min_age=min_age,
            max_age=max_age,
            limit=limit,
            page_size=page_size,
            page_number=page_number,
            as_values=as_values,
            workers=workers,
            **kwargs
        )

    async def get_all_files(
            self,
            expression: str | None = None,
            *,
            before: str | dt.datetime | None = None,
            after: str | dt.datetime | None = None,
            date_from: str | dt.datetime | None = None,
            date_to: str | dt.datetime | None = None,
            min_age: str | dt.timedelta | None = None,
            max_age: str | dt.timedelta | None = None,
            limit: int | None = 5,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
            **kwargs,
    ) -> list[TenantStatisticsFile]:
        return [
            x
            async for x in self._files.select(
                expression,
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
                **kwargs
            )
        ]

    async def generate(
            self,
            *files: TenantStatisticsFile,
            date_from: str | dt.datetime | None = None,
            date_to: str | dt.datetime | None = None,
            workers: int | None = None,
    ):
        return await self._files.generate(*files, date_from=date_from, date_to=date_to, workers=workers)

    async def get_file(self, file_id: str) -> FileDownload:
        return await self._files.get(file_id)

    async def get_latest_file(self, *, month: str | dt.datetime = "today") -> FileDownload:
        return await self._files.get_latest(month=month)