import warnings
from datetime import datetime, timedelta
from enum import StrEnum
from typing import AsyncIterator, Sequence, Self

from pyc8y.rest import CumulocityRestClient
from pyc8y.model.matcher import JsonMatcher
from pyc8y.model.model_base import (
    CumulocityObject,
    json_property,
    datetime_property,
    id_property,
    CumulocityResource,
    map_params,
    resolve_page_size,
    time_property,
)
from pyc8y.types import AlarmMeta


class AlarmSeverity(StrEnum):
    """Alarm severity levels."""

    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"
    MINOR = "MINOR"
    WARNING = "WARNING"


class AlarmStatus(StrEnum):
    """Alarm statuses."""

    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CLEARED = "CLEARED"


class Alarm(CumulocityObject):
    """Represent an instance of an event object in Cumulocity.

    Instances of this class are returned by functions of the corresponding
    Events API. Use this class to create new or update Event objects.

    See also: https://cumulocity.com/api/#tag/Events
    """

    _meta = AlarmMeta

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        *,
        type: str | None = None,  # noqa (type)
        time: str | datetime | None = None,
        source: str | None = None,
        text: str | None = None,
        status: AlarmStatus | str | None = None,
        severity: AlarmSeverity | str | None = None,
        **kwargs,
    ):
        super().__init__(c8y, **kwargs)
        self.type = type
        self.source = source
        self.time = time
        self.text = text
        self.status = status
        self.severity = severity

    type = json_property("type")
    source = id_property("source")
    text = json_property("text")
    time = time_property("time")
    status = json_property("status")
    severity = json_property("severity")
    count = json_property("count")
    datetime = datetime_property("datetime")
    creation_time = json_property("creationTime", read_only=True)
    creation_datetime = datetime_property("creationTime")
    update_time = json_property("lastUpdated", read_only=True)
    update_datetime = datetime_property("lastUpdated")
    last_updated = json_property("lastUpdated", read_only=True)
    last_updated_datetime = datetime_property("lastUpdated")

    async def create(self):
        return await self._create()

    async def update(self, copy: bool = False) -> Self:
        """Update the object within the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated Alarm. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._update(copy)

    async def delete(self, **_) -> None:
        """Delete this object within the database.

        An alarm is identified through its type and source. These fields
        must be defined for this to function. This is always the case if
        the instance was built by the API.

        See also functions `Alarms.delete` and `Alarms.delete_by`
        """
        if not self.type:
            raise ValueError("The alarm type must be set to allow unambiguous identification.")
        if not self.source:
            raise ValueError("The alarm source must be set to allow unambiguous identification.")
        await Alarms(self.c8y).delete_by(type=self.type, source=self.source)

    async def apply_to(self, other_id: str) -> Self:
        """Apply changes made to this object to another object in the database.

        Args:
            other_id (str):  Database ID of the object to update.

        Returns:
            A fresh object representing the updated object's state within
            the database.
        """
        await self._apply_to(other_id)


class Alarms(CumulocityResource[Alarm]):
    _meta = AlarmMeta
    _object_type = Alarm

    async def get(self, id: str) -> Alarm:  # noqa (id)
        """Retrieve a specific object from the database.

        Args:
            id (str): The database ID of the object

        Returns:
            An Alarm instance representing the object in the database.
        """
        return await self._get(id)

    def select(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,
        source: str | None = None,
        status: str | None = None,
        resolved: str | None = None,
        severity: str | None = None,
        fragment: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        created_before: str | datetime | None = None,
        created_after: str | datetime | None = None,
        created_from: str | datetime | None = None,
        created_to: str | datetime | None = None,
        updated_before: str | datetime | None = None,
        updated_after: str | datetime | None = None,
        last_updated_from: str | datetime | None = None,
        last_updated_to: str | datetime | None = None,
        with_source_children: bool | None = None,
        with_source_assets: bool | None = None,
        with_source_devices: bool | None = None,
        with_source_additions: bool | None = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[Alarm]:
        """Query the database for alarms and iterate over the results.

        This function is implemented in a lazy fashion - results will only be
        fetched from the database as long there is a consumer for them.

        All parameters are considered to be filters, limiting the result set
        to objects which meet the filters specification.  Filters can be
        combined (as defined in the Cumulocity REST API).

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            type (str):  Alarm type
            source (str):  Database ID of a source device
            fragment (str):  Name of a present custom/standard fragment
            fragment_type (str): Same as `fragment`.
            status (str):  Alarm status
            severity (str):  Alarm severity
            resolved (str):  Whether the alarm status is CLEARED
            before (str|datetime):  Datetime object or ISO date/time string.
                Only alarms assigned to a time before this date are returned.
            after (str|datetime):  Datetime object or ISO date/time string.
                Only alarms assigned to a time after this date are returned
            date_from (str|datetime): Same as `after`
            date_to (str|datetime): Same as `before`
            min_age (timedelta):  Matches only alarms of at least this age
            max_age (timedelta):  Matches only alarms with at most this age
            created_before (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time before this date are returned.
            created_after (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time after this date are returned.
            created_from (str|datetime): Same as `created_after`
            created_to (str|datetime): Same as `created_before`
            updated_before (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time before this date are returned.
            updated_after (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time after this date are returned.
            last_updated_from (str|datetime): Same as `updated_after`
            last_updated_to (str|datetime): Same as `updated_before`
            with_source_children (bool): Whether also alarms for related source
                children should be included. Requires `source`.
            with_source_assets (bool): Whether also alarms for related source
                assets should be included. Requires `source`.
            with_source_devices (bool): Whether also alarms for related source
                devices should be included. Requires `source`
            with_source_additions (bool): Whether also alarms for related source
                additions should be included. Requires `source`.
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            include (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The inclusion is applied first.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            exclude (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The exclusion is applied second.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int): Pull a specific page; this effectively disables
                automatic follow-up page retrieval.
            as_values: (str|tuple|list[str|tuple]):  Don't parse objects, but
                directly extract the values at certain JSON paths as tuples;
                If the path is not defined in a result, None is used; Specify
                a tuple to define a proper default value for each path.

        Returns:
            Generator of Alarm objects

        See also:
            https://github.com/bytebutcher/pydfql/blob/main/docs/USER_GUIDE.md#4-query-language
        """
        page_size = resolve_page_size(page_size, limit, include, exclude)
        params = (
            map_params(
                type=type,
                source=source,
                status=status,
                resolved=resolved,
                severity=severity,
                fragment=fragment,
                fragment_type=fragment,
                # time
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                created_before=created_before,
                created_after=created_after,
                created_from=created_from,
                created_to=created_to,
                updated_before=updated_before,
                updated_after=updated_after,
                last_updated_from=last_updated_from,
                last_updated_to=last_updated_to,
                # modifiers
                with_source_children=with_source_children,
                with_source_devices=with_source_devices,
                with_source_assets=with_source_assets,
                with_source_additions=with_source_additions,
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
            include=include,
            exclude=exclude,
            as_values=as_values,
            workers=workers,
            preserve_order=False,
        )

    async def get_all(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,
        source: str | None = None,
        status: str | None = None,
        resolved: str | None = None,
        severity: str | None = None,
        fragment: str | None = None,
        with_source_assets: bool | None = None,
        with_source_devices: bool | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        created_before: str | datetime | None = None,
        created_after: str | datetime | None = None,
        created_from: str | datetime | None = None,
        created_to: str | datetime | None = None,
        updated_before: str | datetime | None = None,
        updated_after: str | datetime | None = None,
        last_updated_from: str | datetime | None = None,
        last_updated_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[Alarm]:
        """Query the database for alarms and return the results as list.

        This function is a greedy version of the select function. All
        available results are read immediately and returned as list.

        See `select` for a documentation of arguments.

        Returns:
            List of Alarm objects
        """
        return [
            x
            async for x in self.select(
                expression=expression,
                type=type,
                source=source,
                fragment=fragment,
                status=status,
                severity=severity,
                resolved=resolved,
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                created_before=created_before,
                created_after=created_after,
                created_from=created_from,
                created_to=created_to,
                updated_before=updated_before,
                updated_after=updated_after,
                last_updated_from=last_updated_from,
                last_updated_to=last_updated_to,
                min_age=min_age,
                max_age=max_age,
                with_source_devices=with_source_devices,
                with_source_assets=with_source_assets,
                limit=limit,
                include=include,
                exclude=exclude,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
                **kwargs,
            )
        ]

    async def delete_by(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,
        source: str | None = None,
        fragment: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        resolved: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        created_before: str | datetime | None = None,
        created_after: str | datetime | None = None,
        created_from: str | datetime | None = None,
        created_to: str | datetime | None = None,
        updated_before: str | datetime | None = None,
        updated_after: str | datetime | None = None,
        last_updated_from: str | datetime | None = None,
        last_updated_to: str | datetime | None = None,
        with_source_children: bool | None = None,
        with_source_assets: bool | None = None,
        with_source_devices: bool | None = None,
        with_source_additions: bool | None = None,
        **kwargs,
    ):
        """Query the database and delete matching alarms.

        All parameters are considered to be filters, limiting the result set
        to objects which meet the filters specification. Filters can be
        combined (as defined in the Cumulocity REST API).

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            type (str):  Alarm type
            source (str):  Database ID of a source device
            fragment (str):  Name of a present custom/standard fragment
            status (str):  Alarm status
            severity (str):  Alarm severity
            resolved (str):  Whether the alarm status is CLEARED
            before (str|datetime):  Datetime object or ISO date/time string.
                Only alarms assigned to a time before this date are returned.
            after (str|datetime):  Datetime object or ISO date/time string.
                Only alarms assigned to a time after this date are returned
            date_from (str|datetime): Same as `after`
            date_to (str|datetime): Same as `before`
            min_age (timedelta):  Matches only alarms of at least this age
            max_age (timedelta):  Matches only alarms with at most this age
            created_before (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time before this date are returned.
            created_after (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time after this date are returned.
            created_from (str|datetime): Same as `created_after`
            created_to (str|datetime): Same as `created_before`
            updated_before (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time before this date are returned.
            updated_after (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time after this date are returned.
            last_updated_from (str|datetime): Same as `updated_after`
            last_updated_to (str|datetime): Same as `updated_before`
            with_source_children (bool): Whether also alarms for related source
                children should be included. Requires `source`.
            with_source_assets (bool): Whether also alarms for related source
                assets should be included. Requires `source`.
            with_source_devices (bool): Whether also alarms for related source
                devices should be included. Requires `source`
            with_source_additions (bool): Whether also alarms for related source
                additions should be included. Requires `source`
        """
        if expression:
            await self.c8y.delete(f"{self.resource_path}?{expression}")
            return
        params = map_params(
            type=type,
            source=source,
            status=status,
            resolved=resolved,
            severity=severity,
            fragment=fragment,
            fragment_type=fragment,
            # time
            before=before,
            after=after,
            date_from=date_from,
            date_to=date_to,
            min_age=min_age,
            max_age=max_age,
            created_before=created_before,
            created_after=created_after,
            created_from=created_from,
            created_to=created_to,
            updated_before=updated_before,
            updated_after=updated_after,
            last_updated_from=last_updated_from,
            last_updated_to=last_updated_to,
            # modifiers
            with_source_children=with_source_children,
            with_source_devices=with_source_devices,
            with_source_assets=with_source_assets,
            with_source_additions=with_source_additions,
            **kwargs,
        )
        await self.c8y.delete(self.resource_path, params=params)

    async def count(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,
        source: str | None = None,
        status: str | None = None,
        resolved: str | None = None,
        severity: str | None = None,
        fragment: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        with_source_children: bool | None = None,
        with_source_assets: bool | None = None,
        with_source_devices: bool | None = None,
        with_source_additions: bool | None = None,
        **kwargs,
    ) -> int:
        """Count the number of certain alarms.

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            type (str):  Alarm type
            source (str):  Database ID of a source device
            fragment (str):  Name of a present custom/standard fragment
            status (str):  Alarm status
            severity (str):  Alarm severity
            resolved (str):  Whether the alarm status is CLEARED
            before (str|datetime):  Datetime object or ISO date/time string.
                Only alarms assigned to a time before this date are returned.
            after (str|datetime):  Datetime object or ISO date/time string.
                Only alarms assigned to a time after this date are returned
            date_from (str|datetime): Same as `after`
            date_to (str|datetime): Same as `before`
            min_age (timedelta):  Matches only alarms of at least this age
            max_age (timedelta):  Matches only alarms with at most this age
            with_source_children (bool): Whether also alarms for related source
                children should be included. Requires `source`.
            with_source_assets (bool): Whether also alarms for related source
                assets should be included. Requires `source`.
            with_source_devices (bool): Whether also alarms for related source
                devices should be included. Requires `source`
            with_source_additions (bool): Whether also alarms for related source
                additions should be included. Requires `source`

        Returns:
            Number of matching alarms in Cumulocity.
        """
        # the count endpoint returns a plain int, not JSON, but it still can be parsed by orjson
        if expression:
            return await self.c8y.get(f"{self.resource_path}/count?{expression}", accept="text/plain")
        params = map_params(
            type=type,
            source=source,
            status=status,
            resolved=resolved,
            severity=severity,
            fragment=fragment,
            fragment_type=fragment,
            # time
            before=before,
            after=after,
            date_from=date_from,
            date_to=date_to,
            min_age=min_age,
            max_age=max_age,
            # modifiers
            with_source_children=with_source_children,
            with_source_devices=with_source_devices,
            with_source_assets=with_source_assets,
            with_source_additions=with_source_additions,
            **kwargs,
        )
        return await self.c8y.get(f"{self.resource_path}/count", params=params, accept="text/plain")

    async def get_count(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,
        source: str | None = None,
        status: str | None = None,
        resolved: str | None = None,
        severity: str | None = None,
        fragment: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        with_source_children: bool | None = None,
        with_source_assets: bool | None = None,
        with_source_devices: bool | None = None,
        with_source_additions: bool | None = None,
        **kwargs,
    ) -> int:
        """Count the number of certain alarms.

        Note: Unlike other collection classes, Alarms has a dedicated
        /alarms/count endpoint. Consider using count() directly.

        See `count` for a documentation of arguments.

        Returns:
            Number of matching alarms in Cumulocity.
        """
        warnings.warn(
            "Alarms has a dedicated /alarms/count endpoint; prefer using count() directly.",
            UserWarning,
            stacklevel=2,
        )
        return await self.count(
            expression,
            type=type,
            source=source,
            status=status,
            resolved=resolved,
            severity=severity,
            fragment=fragment,
            before=before,
            after=after,
            date_from=date_from,
            date_to=date_to,
            min_age=min_age,
            max_age=max_age,
            with_source_children=with_source_children,
            with_source_assets=with_source_assets,
            with_source_devices=with_source_devices,
            with_source_additions=with_source_additions,
            **kwargs,
        )

    async def create(self, *alarms: Alarm, workers: int | None = None) -> None:
        """Create alarm objects within the database.

        Args:
            *alarms (Alarm): Collection of Alarm instances
            workers (int): The number of parallel processes to use
        """
        await self._create(*alarms, workers=workers)

    async def update(self, *alarms: Alarm, workers: int | None = None) -> None:
        """Write changes to the database.

        Args:
            *alarms (Alarm): Collection of Alarm instances
            workers (int): The number of parallel processes to use
        """
        await self._update(*alarms, workers=workers)

    async def delete(self, *alarms: str | Alarm, workers: int | None = None) -> None:
        """Delete alarm objects from the database.

        Args:
            *alarms (str | Alarm): Collection of Alarm instances or IDs
            workers (int): The number of parallel processes to use
        """
        await self._delete(*alarms, workers=workers)

    async def apply_to(self, alarm: Alarm | dict, *alarm_ids: str, workers: int | None = None):
        """Apply changes made to a single instance to other objects in the database.

        Args:
            alarm (Alarm|dict): Object serving as model for the update or
                simply a dictionary representing the diff JSON.
            *alarm_ids (str): A collection of database IDS of alarms
            workers (int): The number of parallel processes to use
        """
        await self._apply_to(alarm, *alarm_ids, workers=workers)

    async def apply_by(
        self,
        alarm: dict | Alarm,
        expression: str | None = None,
        *,
        type: str | None = None,
        source: str | None = None,
        fragment: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        resolved: str | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        created_before: str | datetime | None = None,
        created_after: str | datetime | None = None,
        created_from: str | datetime | None = None,
        created_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        with_source_children: bool | None = None,
        with_source_assets: bool | None = None,
        with_source_devices: bool | None = None,
        with_source_additions: bool | None = None,
        **kwargs,
    ):
        """Apply changes made to a single instance to other objects in the database.

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            alarm (Alarm): Object serving as model for the update
            type (str):  Alarm type
            source (str):  Database ID of a source device
            fragment (str):  Name of a present custom/standard fragment
            status (str):  Alarm status
            severity (str):  Alarm severity
            resolved (str):  Whether the alarm status is CLEARED
            before (str|datetime):  Datetime object or ISO date/time string.
                Only alarms assigned to a time before this date are returned.
            after (str|datetime):  Datetime object or ISO date/time string.
                Only alarms assigned to a time after this date are returned
            created_before (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time before this date are returned.
            created_after (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time after this date are returned.
            date_from (str|datetime): Same as `after`
            date_to (str|datetime): Same as `before`
            created_from (str|datetime): Same as `created_after`
            created_to (str|datetime): Same as `created_before`
            min_age (timedelta):  Matches only alarms of at least this age
            max_age (timedelta):  Matches only alarms with at most this age
            with_source_children (bool): Whether also alarms for related source
                children should be included. Requires `source`.
            with_source_assets (bool): Whether also alarms for related source
                assets should be included. Requires `source`.
            with_source_devices (bool): Whether also alarms for related source
                devices should be included. Requires `source`
            with_source_additions (bool): Whether also alarms for related source
                additions should be included. Requires `source`.

        See also: https://cumulocity.com/api/#operation/putAlarmCollectionResource
        """
        alarm_json = alarm if isinstance(alarm, dict) else alarm._staged_json
        if expression:
            await self.c8y.put(
                f"{self.resource_path}?{expression}",
                json=alarm_json,
                content_type=self._meta.collection_mime_type,
                accept=None,
            )
            return
        params = map_params(
            type=type,
            source=source,
            status=status,
            resolved=resolved,
            severity=severity,
            fragment=fragment,
            fragment_type=fragment,
            # time
            before=before,
            after=after,
            date_from=date_from,
            date_to=date_to,
            min_age=min_age,
            max_age=max_age,
            created_before=created_before,
            created_after=created_after,
            created_from=created_from,
            created_to=created_to,
            # modifiers
            with_source_children=with_source_children,
            with_source_devices=with_source_devices,
            with_source_assets=with_source_assets,
            with_source_additions=with_source_additions,
            **kwargs,
        )
        await self.c8y.put(
            self.resource_path,
            params=params,
            json=alarm_json,
            content_type=self._meta.collection_mime_type,
            accept=None,
        )
