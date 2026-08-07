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
    """Device-level statistics for a single day or month.

    See also: https://cumulocity.com/api/core/#tag/Device-statistics
    """


class UsageStatistics(JsonObject):
    """Tenant-level usage statistics for a period.

    See also: https://cumulocity.com/api/core/#tag/Usage-statistics
    """


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

        async def fetch_page(page: int, **_) -> list:
            result = await self.c8y.get(
                resource, params=(("currentPage", str(page)), ("pageSize", str(page_size or 5)))
            )
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

        async def fetch_page(page: int, **_) -> list:
            result = await self.c8y.get(
                resource, params=(("currentPage", str(page)), ("pageSize", str(page_size or 5)))
            )
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
    """Represents a tenant statistics file within the database.

    Instances of this class are returned by functions of the corresponding
    TenantStatistics API. Use this class to generate new statistics files.

    See also: https://cumulocity.com/api/core/#tag/Usage-statistics
    """

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

    async def generate(self, copy: bool = False) -> Self:
        """Generate the statistics file within the database.

        Note: This can only be invoked from the management tenant.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The created TenantStatisticsFile. By default, this is `self`; if
            `copy=True`, a fresh instance.
        """
        return await self._create(copy)

    async def read(self) -> FileDownload:
        """Download this statistics file from the database.

        Returns:
            FileDownload object wrapping file content and file name.
        """
        self._assert_c8y()
        self._assert_key()
        return await self.c8y.get_file(self.object_path)

    async def create(self, copy: bool = False) -> Self:
        """Create (generate) the statistics file within the database.

        Note: This can only be invoked from the management tenant.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The created TenantStatisticsFile. By default, this is `self`; if
            `copy=True`, a fresh instance.
        """
        return await self.generate(copy)


class _StatisticsFiles(CumulocityResource):
    """Internal resource for /tenant/statistics/files.

    Note: Every operation on this resource can only be invoked from the
    management tenant.
    """

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

    See also: https://cumulocity.com/api/core/#tag/Device-statistics and https://cumulocity.com/api/core/#tag/Usage-statistics
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
        """Iterate over a tenant's daily device statistics.

        Args:
            tenant_id (str):  Database ID of the tenant
            date (str | datetime):  The day to read statistics for
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit`.
            page_number (int):  Pull a specific page only; this effectively disables
                automatic follow-up page retrieval.
            as_values: (*str|tuple):  Don't parse objects, but directly extract
                the values at certain JSON paths as tuples; If the path is not
                defined in a result, None is used; Specify a tuple to define
                a proper default value for each path.
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of DeviceStatistics instances
        """
        return self._daily.select(
            tenant_id,
            date,
            limit=limit,
            page_size=page_size,
            page_number=page_number,
            as_values=as_values,
            workers=workers,
        )

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
        """Query the database for a tenant's daily device statistics and
        return the results as list.

        See `select_daily_device_statistics` for a documentation of arguments.

        Returns:
            List of DeviceStatistics instances
        """
        return [
            x
            async for x in self._daily.select(
                tenant_id,
                date,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
            )
        ]

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
        """Iterate over a tenant's monthly device statistics.

        Args:
            tenant_id (str):  Database ID of the tenant
            date (str | datetime):  The month to read statistics for
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit`.
            page_number (int):  Pull a specific page only; this effectively disables
                automatic follow-up page retrieval.
            as_values: (*str|tuple):  Don't parse objects, but directly extract
                the values at certain JSON paths as tuples; If the path is not
                defined in a result, None is used; Specify a tuple to define
                a proper default value for each path.
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of DeviceStatistics instances
        """
        return self._monthly.select(
            tenant_id,
            date,
            limit=limit,
            page_size=page_size,
            page_number=page_number,
            as_values=as_values,
            workers=workers,
        )

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
        """Query the database for a tenant's monthly device statistics and
        return the results as list.

        See `select_monthly_device_statistics` for a documentation of arguments.

        Returns:
            List of DeviceStatistics instances
        """
        return [
            x
            async for x in self._monthly.select(
                tenant_id,
                date,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
            )
        ]

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
        """Query the database for usage statistics and iterate over the results.

        Note: Results are restricted to your own tenant unless invoked from
        the management tenant.

        Args:
            expression (str):  Arbitrary filter expression; all other filters
                are ignored if this is provided
            before (str | datetime):  Include only results before this date
            after (str | datetime):  Include only results after this date
            date_from (str | datetime):  Include only results from this date
            date_to (str | datetime):  Include only results up to this date
            min_age (str | timedelta):  Include only results at least this old
            max_age (str | timedelta):  Include only results at most this old
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int):  Pull a specific page only; this effectively disables
                automatic follow-up page retrieval.
            as_values: (*str|tuple):  Don't parse objects, but directly extract
                the values at certain JSON paths as tuples; If the path is not
                defined in a result, None is used; Specify a tuple to define
                a proper default value for each path.
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of UsageStatistics instances
        """
        return self._usage.select(
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
            **kwargs,
        )

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
        """Query the database for usage statistics and return the results as list.

        See `select_usage_statistics` for a documentation of arguments.

        Returns:
            List of UsageStatistics instances
        """
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
        """Retrieve a tenant's usage statistics summary.

        Note: Passing a `tenant_id` other than your own requires management
        tenant access; omit it to read the current tenant's summary.

        Args:
            tenant_id (str):  Database ID of the tenant to read the summary
                for; defaults to the current tenant
            before (str | datetime):  Include only results before this date
            after (str | datetime):  Include only results after this date
            date_from (str | datetime):  Include only results from this date
            date_to (str | datetime):  Include only results up to this date
            min_age (str | timedelta):  Include only results at least this old
            max_age (str | timedelta):  Include only results at most this old

        Returns:
            UsageStatistics summary
        """
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
        """Retrieve the aggregated usage statistics summary across all tenants.

        Note: This can only be invoked from the management tenant.

        Args:
            before (str | datetime):  Include only results before this date
            after (str | datetime):  Include only results after this date
            date_from (str | datetime):  Include only results from this date
            date_to (str | datetime):  Include only results up to this date
            min_age (str | timedelta):  Include only results at least this old
            max_age (str | timedelta):  Include only results at most this old

        Returns:
            UsageStatistics summary
        """
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
        """Query the database for statistics files and iterate over the results.

        Note: This can only be invoked from the management tenant.

        Args:
            expression (str):  Arbitrary filter expression; all other filters
                are ignored if this is provided
            before (str | datetime):  Include only results before this date
            after (str | datetime):  Include only results after this date
            date_from (str | datetime):  Include only results from this date
            date_to (str | datetime):  Include only results up to this date
            min_age (str | timedelta):  Include only results at least this old
            max_age (str | timedelta):  Include only results at most this old
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int):  Pull a specific page only; this effectively disables
                automatic follow-up page retrieval.
            as_values: (*str|tuple):  Don't parse objects, but directly extract
                the values at certain JSON paths as tuples; If the path is not
                defined in a result, None is used; Specify a tuple to define
                a proper default value for each path.
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of TenantStatisticsFile instances
        """
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
        """Query the database for statistics files and return the results as list.

        Note: This can only be invoked from the management tenant.

        See `select_files` for a documentation of arguments.

        Returns:
            List of TenantStatisticsFile instances
        """
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
        """Generate one or more statistics files within the database.

        If `files` is omitted, a single file covering `date_from` to `date_to`
        is generated.

        Note: This can only be invoked from the management tenant.

        Args:
            *files (TenantStatisticsFile):  Collection of TenantStatisticsFile
                instances to generate
            date_from (str | datetime):  Start date of the file to generate;
                only used if `files` is not given
            date_to (str | datetime):  End date of the file to generate;
                only used if `files` is not given
            workers (int):  Number of parallel workers
        """
        return await self._files.generate(*files, date_from=date_from, date_to=date_to, workers=workers)

    async def get_file(self, file_id: str) -> FileDownload:
        """Download a specific statistics file.

        Note: This can only be invoked from the management tenant.

        Args:
            file_id (str):  Database ID of the statistics file

        Returns:
            FileDownload wrapping the file content and name
        """
        return await self._files.get(file_id)

    async def get_latest_file(self, *, month: str | dt.datetime = "today") -> FileDownload:
        """Download the latest statistics file for a given month.

        Note: This can only be invoked from the management tenant.

        Args:
            month (str | datetime):  The month to read the latest file for;
                defaults to the current month

        Returns:
            FileDownload wrapping the file content and name
        """
        return await self._files.get_latest(month=month)
