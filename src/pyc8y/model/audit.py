# Copyright (c) 2026 Christoph Souris

import dataclasses
from datetime import datetime, timedelta
from enum import StrEnum
from typing import AsyncIterator, ClassVar, Self, Sequence

from pyc8y.rest import CumulocityRestClient
from pyc8y.model.matcher import JsonMatcher
from pyc8y.model.model_base import (
    CumulocityObject,
    CumulocityResource,
    json_property,
    datetime_property,
    id_property,
    time_property,
    map_params,
    resolve_page_size,
)
from pyc8y.types import AuditRecordMeta


@dataclasses.dataclass
class Change:
    """Change details fragment within an audit log."""

    attribute: str = None
    new_value: str = None
    previous_value: str = None
    type: str = None  # noqa (type)

    @classmethod
    def from_json(cls, json: dict) -> Self:
        return cls(
            attribute=json.get("attribute"),
            new_value=json.get("newValue"),
            previous_value=json.get("previousValue"),
            type=json.get("type"),
        )

    def to_json(self) -> dict:
        result = {}
        if self.attribute is not None:
            result["attribute"] = self.attribute
        if self.new_value is not None:
            result["newValue"] = self.new_value
        if self.previous_value is not None:
            result["previousValue"] = self.previous_value
        if self.type is not None:
            result["type"] = self.type
        return result


class Severity(StrEnum):
    """Audit severity levels."""

    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"
    MINOR = "MINOR"
    WARNING = "WARNING"
    INFORMATION = "information"  # for whatever reason, lowercase is correct


class Type(StrEnum):
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


class AuditRecord(CumulocityObject):
    """Represents an Audit Record object within Cumulocity.

    Instances of this class are returned by functions of the corresponding
    Audits API. Use this class to create new AuditRecord objects.

    See also: https://cumulocity.com/api/core/#tag/Audits
    """

    _meta = AuditRecordMeta
    _change_type: ClassVar[type[Change]] = Change

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
        raw: list | None = self._json.get("changes")
        if raw is None:
            return None
        return tuple(self._change_type.from_json(x) for x in raw)

    @changes.setter
    def changes(self, value: Sequence[Change] | None):
        if value is not None:
            self._staged_json["changes"] = [c.to_json() for c in value]

    async def create(self) -> Self:
        """Create the AuditRecord within the database.

        Returns:
            A fresh AuditRecord object representing what was created within the database.
        """
        return await self._create()


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
        reverse: bool | None = None,
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
            reverse (bool):  Invert the order of results
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
                reverse=reverse,
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
        reverse: bool | None = None,
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
                reverse=reverse,
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

    async def create(self, *records: AuditRecord, workers: int | None = None) -> None:
        """Create audit record objects within the database.

        Args:
            *records (AuditRecord):  Collection of AuditRecord instances
            workers (int): The number of parallel processes to use
        """
        await self._create(*records, workers=workers)
