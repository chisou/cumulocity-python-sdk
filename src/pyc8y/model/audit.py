# Copyright (c) 2026 Christoph Souris

from datetime import datetime, timedelta
from enum import StrEnum
from typing import AsyncIterator, Self, Sequence

from pyc8y.rest import CumulocityRestClient
from pyc8y.model.matcher import JsonMatcher
from pyc8y.model.model_base import (
    CumulocityObject,
    CumulocityResource,
    JsonObject,
    WithId,
    json_property,
    datetime_property,
    id_property,
    time_property,
    map_params,
    resolve_page_size,
)
from pyc8y.model.alarm import Alarm
from pyc8y.model.application import Application
from pyc8y.model.event import Event
from pyc8y.model.user import User, UserGroup, InventoryRole
from pyc8y.model.managed_object import ManagedObject
from pyc8y.model.operation import Operation, BulkOperation
from pyc8y.types import AuditRecordMeta


class Change(JsonObject):
    """Change details fragment within an audit log."""

    attribute = json_property[str]("attribute")
    new_value = json_property[str]("newValue")
    previous_value = json_property[str]("previousValue")
    type = json_property[str]("type")

    def __init__(
        self,
        data: dict | None = None,
        *,
        attribute: str | None = None,
        new_value: str | None = None,
        previous_value: str | None = None,
        type: str | None = None,  # noqa (type)
    ):
        if data is not None:
            super().__init__(data)
        else:
            super().__init__()
            self.attribute = attribute
            self.new_value = new_value
            self.previous_value = previous_value
            self.type = type


class AuditSeverity(StrEnum):
    """Audit severity levels."""

    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"
    MINOR = "MINOR"
    WARNING = "WARNING"
    INFORMATION = "information"  # for whatever reason, lowercase is correct


class AuditType(StrEnum):
    """Audit record source types."""

    ALARM = "Alarm"
    APPLICATION = "Application"
    BULKOPERATION = "BulkOperation"
    CEPMODULE = "CepModule"
    CONNECTOR = "Connector"
    EVENT = "Event"
    GROUP = "Group"
    INVENTORY = "Inventory"
    INVENTORYROLE = "InventoryRole"
    OPERATION = "Operation"
    OPTION = "Option"
    REPORT = "Report"
    SINGLESIGNON = "SingleSignOn"
    SMARTRULE = "SmartRule"
    SYSTEM = "SYSTEM"
    TENANT = "Tenant"
    TENANT_AUTH_CONFIG = "TenantAuthConfig"
    TRUSTED_CERTIFICATES = "TrustedCertificates"
    USER = "User"
    USER_AUTHENTICATION = "UserAuthentication"


class AuditRecord(WithId, CumulocityObject):
    """Represents an Audit Record object within Cumulocity.

    Instances of this class are returned by functions of the corresponding
    Audits API. Use this class to create new AuditRecord objects.

    See also: https://cumulocity.com/api/core/#tag/Audits
    """

    _meta = AuditRecordMeta

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        *,
        type: str | None = None,  # noqa (type)
        time: str | datetime | None = None,
        source: str | None = None,
        activity: str | None = None,
        text: str | None = None,
        changes: list[Change] | None = None,
        severity: str | None = None,
        application: str | None = None,
        user: str | None = None,
        **kwargs,
    ):
        super().__init__(c8y, **kwargs)
        self.type = type
        self.time = time
        self.source = source
        self.activity = activity
        self.text = text
        self.changes = changes
        self.severity = severity
        self.application = application
        self.user = user

    type = json_property("type")
    time = time_property("time")
    datetime = datetime_property("time")
    source = id_property("source")
    activity = json_property("activity")
    text = json_property("text")
    severity = json_property("severity")
    application = json_property("application")
    user = json_property("user")
    creation_time = json_property("creationTime", read_only=True)
    creation_datetime = datetime_property("creationTime")

    @property
    def changes(self) -> tuple[Change, ...] | None:
        """Return the changes recorded in this audit record."""
        raw: list | None = self.json.get("changes")
        if raw is None:
            return None
        return tuple(Change(x) for x in raw)

    @changes.setter
    def changes(self, value: Sequence[Change] | None):
        if value is not None:
            self._staged_json["changes"] = list(value)

    async def create(self, copy: bool = False) -> Self:
        """Create the AuditRecord within the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The created AuditRecord. By default, this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._create(copy)


class AuditRecords(CumulocityResource[AuditRecord]):
    """Provides access to the Audit API.

    This class can be used for get, search for, and create
    audit records within the Cumulocity database.

    See also: https://cumulocity.com/api/core/#tag/Audits
    """

    _meta = AuditRecordMeta
    _object_type = AuditRecord

    async def get(self, record_id: str) -> AuditRecord:
        """Retrieve a specific audit record from the database.

        Args:
            record_id (str):  The database ID of the audit record

        Returns:
            An AuditRecord instance
        """
        return await self._get(record_id)

    def select(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,  # noqa (type)
        source: str | None = None,
        application: str | None = None,
        user: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
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
    ) -> AsyncIterator[AuditRecord]:
        """Query the database for audit records and iterate over the results.

        This function is implemented in a lazy fashion - results will only be
        fetched from the database as long as there is a consumer for them.

        Args:
            expression (str):  Arbitrary filter expression; all other filters
                are ignored if this is provided
            type (str):  Audit record type
            source (str):  Database ID of a source device
            application (str):  Application from which the audit was carried out
            user (str):  The user who carried out the activity
            before (str|datetime):  Only records before this date
            after (str|datetime):  Only records after this date
            date_from (str|datetime):  Same as `after`
            date_to (str|datetime):  Same as `before`
            min_age (timedelta|str):  Minimum age for selected records
            max_age (timedelta|str):  Maximum age for selected records
            include (str|JsonMatcher):  Client-side inclusion filter
            exclude (str|JsonMatcher):  Client-side exclusion filter
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int):  Pull a specific page only
            as_values:  Extract values at JSON paths as tuples
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of AuditRecord objects
        """
        page_size = resolve_page_size(page_size, limit, include, exclude)
        params = (
            map_params(
                type=type,
                source=source,
                application=application,
                user=user,
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
        type: str | None = None,  # noqa (type)
        source: str | None = None,
        application: str | None = None,
        user: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
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
    ) -> list[AuditRecord]:
        """Query the database for audit records and return the results as list.

        See `select` for a documentation of arguments.

        Returns:
            List of AuditRecord objects
        """
        return [
            x
            async for x in self.select(
                expression=expression,
                type=type,
                source=source,
                application=application,
                user=user,
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                include=include,
                exclude=exclude,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
                **kwargs,
            )
        ]

    async def get_count(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,  # noqa (type)
        source: str | None = None,
        application: str | None = None,
        user: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        **kwargs,
    ) -> int:
        """Calculate the number of potential results of a database query.

        This function uses the same parameters as the `select` function.

        Returns:
            Number of potential results
        """
        params = (
            map_params(
                type=type,
                source=source,
                application=application,
                user=user,
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                **kwargs,
            )
            if not expression
            else ()
        )
        return await self._get_count(expression=expression, params=params)

    def select_for(
            self,
            obj: CumulocityObject,
            *,
            application: str | None = None,
            user: str | None = None,
            before: str | datetime | None = None,
            after: str | datetime | None = None,
            date_from: str | datetime | None = None,
            date_to: str | datetime | None = None,
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
    ) -> AsyncIterator[AuditRecord]:
        """Query the database for audit records related to a specific object
        and iterate over the results.

        Currently supported object types are: Alarm, Event, Operation,
        BulkOperation, ManagedObject (incl. Device, DeviceGroup, ...), User,
        UserGroup, InventoryRole.

        This function is implemented in a lazy fashion - results will only be
        fetched from the database as long as there is a consumer for them.

        Args:
            obj (CumulocityObject):  An existing object within the database,
                e.g. an Operation, Event, Device, etc.
            application (str):  Application from which the audit was carried out
            user (str):  The user who carried out the activity
            before (str|datetime):  Only records before this date
            after (str|datetime):  Only records after this date
            date_from (str|datetime):  Same as `after`
            date_to (str|datetime):  Same as `before`
            min_age (timedelta|str):  Minimum age for selected records
            max_age (timedelta|str):  Maximum age for selected records
            include (str|JsonMatcher):  Client-side inclusion filter
            exclude (str|JsonMatcher):  Client-side exclusion filter
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int):  Pull a specific page only
            as_values:  Extract values at JSON paths as tuples
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of AuditRecord objects
        """
        source = obj.get("id", None)
        type = ""
        if isinstance(obj, Alarm):
            type = AuditType.ALARM
        elif isinstance(obj, Application):
            type = AuditType.APPLICATION
        elif isinstance(obj, Event):
            type = AuditType.EVENT
        elif isinstance(obj, InventoryRole):
            type = AuditType.INVENTORYROLE
        elif isinstance(obj, ManagedObject):
            type = AuditType.INVENTORY
        elif isinstance(obj, Operation):
            type = AuditType.OPERATION
        elif isinstance(obj, BulkOperation):
            type = AuditType.BULKOPERATION
        elif isinstance(obj, UserGroup):
            type = AuditType.GROUP
        elif isinstance(obj, User):
            source = obj.username
            type = AuditType.USER
        else:
            raise ValueError(f"Unsupported object type {obj.__class__.__name__}.")
        return self.select(
            source=source,
            type=type,
            application=application,
            user=user,
            before=before,
            after=after,
            date_from=date_from,
            date_to=date_to,
            min_age=min_age,
            max_age=max_age,
            include=include,
            exclude=exclude,
            limit=limit,
            page_size=page_size,
            page_number=page_number,
            as_values=as_values,
            workers=workers,
            **kwargs,
        )

    async def get_all_for(
            self,
            obj: CumulocityObject,
            *,
            application: str | None = None,
            user: str | None = None,
            before: str | datetime | None = None,
            after: str | datetime | None = None,
            date_from: str | datetime | None = None,
            date_to: str | datetime | None = None,
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
    ) -> list[AuditRecord]:
        """Query the database for audit records related to a specific object
        and return the result as list.

        This function is a greedy version of the `select` function. All
        available results are read immediately and returned as list.

        See `select` for a documentation of arguments.

        Returns:
            List of AuditRecord objects
        """
        return [
            x
            async for x in self.select_for(
                obj,
                application=application,
                user=user,
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                include=include,
                exclude=exclude,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
                **kwargs,
            )
        ]

    async def create(self, *records: AuditRecord, workers: int | None = None) -> None:
        """Create audit record objects within the database.

        Args:
            *records (AuditRecord):  Collection of AuditRecord instances
            workers (int): The number of parallel processes to use
        """
        await self._create(*records, workers=workers)
