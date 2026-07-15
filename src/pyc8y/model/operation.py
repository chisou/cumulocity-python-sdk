# Copyright (c) 2026 Christoph Souris

from datetime import datetime, timedelta
from enum import StrEnum
from typing import AsyncIterator, Self, Sequence, NamedTuple

from pyc8y.base_util import unwrap_args
from pyc8y.model.model_util import to_datetime
from pyc8y.rest import CumulocityRestClient
from pyc8y.model.inventory import Device
from pyc8y.model.matcher import JsonMatcher
from pyc8y.model.model_base import (
    CumulocityObject,
    CumulocityResource,
    WithId,
    json_property,
    datetime_property,
    expression_implies_order,
    time_property,
    map_params,
    resolve_page_size,
    run_batched,
    ensure_ids,
    skim_latest_by,
)
from pyc8y.types import OperationMeta, BulkOperationMeta


class OperationStatus(StrEnum):
    """Operation statuses."""

    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"


class OperationStatusChange(NamedTuple):
    """Operation status change."""

    time: str
    status: OperationStatus

    @property
    def datetime(self) -> datetime:
        return to_datetime(self.time)


class Operation(WithId, CumulocityObject):
    """Represents an instance of an operation object in Cumulocity.

    Instances of this class are returned by functions of the corresponding
    Operation API. Use this class to create new or update existing operations.

    See also: https://cumulocity.com/api/core/#tag/Operations
    """

    _meta = OperationMeta

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        *,
        device_id: str | None = None,
        description: str | None = None,
        status: str | None = None,
        **kwargs,
    ):
        super().__init__(c8y, **kwargs)
        self.device_id = device_id
        self.description = description
        self.status = status

    bulk_operation_id = json_property("bulkOperationId")
    device_id = json_property("deviceId")
    description = json_property("description")
    status = json_property("status")
    creation_time = json_property("creationTime", read_only=True)
    creation_datetime = datetime_property("creationTime")

    def resolve_type(self) -> str | None:
        """Try to resolve the operation type using a simple heuristic.

        The operation's type is assumed to be the name of an _underscore_
        fragment, e.g. c8y_Command or c8y_Restart. It is assumed that such
        fragment is unambiguous. If no such fragment is found, the first
        non-standard fragment is returned or None if there is none.

        Returns:
            The heuristically determined operation type.
        """
        candidate = next(filter(lambda x: "_" in x, self.keys()), None)
        if candidate is not None:
            return candidate

        def fits_criteria(x):
            return x not in {
                "self",
                "id",
                "bulkOperationId",
                "creationTime",
                "status",
                "description",
                "delivery",
            } and not x.startswith("device")

        return next(filter(fits_criteria, self.keys()), None)

    def get_status_changes(self) -> list[OperationStatusChange]:
        """Retrieve the operation status changes as simple list.

        Returns:
            A list of OperationStatusChange objects as defined in the
            object's JSON (`delivery.log`).
        """
        return [OperationStatusChange(x["time"], x["status"]) for x in self.get("delivery.log", [])]

    async def create(self, copy: bool = False) -> Self:
        """Store the Operation within the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The created Operation. By default, this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._create(copy)

    async def update(self, copy: bool = False) -> Self:
        """Update the Operation within the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated Operation. By default, this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._update(copy)

    async def send_to(self, *devices: str | Device, workers: int | None = None) -> None:
        """Send the Operation to devices within the database.

        Args:
            *devices (str | Device): A collection of devices or device IDs
            workers (int): The number of parallel processes to use
        """
        self._assert_c8y()
        skip_keys = {"creationTime", "delivery", "id", "self", "status", "deviceId", "deviceName"}
        operation_json = {k: v for k, v in self.json.items() if k not in skip_keys}
        await run_batched(
            ensure_ids(unwrap_args(devices)),
            workers,
            lambda x: self.c8y.post(self.resource_path, json=operation_json | {"deviceId": x}, accept=None),
        )


class Operations(CumulocityResource[Operation]):
    """Provides access to the Operations API.

    This class can be used for get, search for, create, update and
    delete operations within the Cumulocity database.

    See also: https://cumulocity.com/api/core/#tag/Operations
    """

    _meta = OperationMeta
    _object_type = Operation

    async def get(self, operation_id: str) -> Operation:
        """Read a specific operation from the database.

        Args:
            operation_id (str):  Database ID of the operation

        Returns:
            Operation object
        """
        return await self._get(str(operation_id))

    async def skim_latest(
        self,
        device_id: str | None = None,
        *,
        max_age: str | timedelta | None = None,
        limit: int | None = 200,
        **kwargs,
    ) -> dict[str, Operation]:
        """Best-effort assembly of the latest operation of each type.

        Scans the most recent operations and returns the latest one seen
        for each type, as resolved by `Operation.resolve_type`. Intended
        for quick, interactive exploration this is NOT guaranteed to be
        complete - a type that hasn't occurred within the scanned window
        is silently missing from the result.

        Args:
            device_id (str):  Database ID of device
            max_age (timedelta|str):  How far back to scan; takes
                precedence over `limit` if given.
            limit (int):  Maximum number of operations to scan; default
                200. Ignored if `max_age` is given.
            kwargs:  Additional filters, forwarded to `get_all`.

        Returns:
            Mapping of resolved operation type to the latest matching
                Operation seen within the scanned window.
        """
        if max_age is not None:
            limit = None
        operations = await self.get_all(device_id=device_id, max_age=max_age, limit=limit, asc=False, **kwargs)
        return skim_latest_by(operations, key=lambda o: o.resolve_type())

    def select(
        self,
        expression: str | None = None,
        *,
        agent_id: str | None = None,
        device_id: str | None = None,
        status: str | None = None,
        bulk_id: str | None = None,
        fragment: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        asc: bool | None = None,
        revert: bool | None = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[Operation]:
        """Query the database for operations and iterate over the results.

        This function is implemented in a lazy fashion - results will only be
        fetched from the database as long as there is a consumer for them.

        Args:
            expression (str):  Arbitrary filter expression; all other filters
                are ignored if this is provided
            agent_id (str):  Database ID of agent
            device_id (str):  Database ID of device
            status (str):  Operation status
            bulk_id (str):  The bulk operation ID that this object belongs to
            fragment (str):  Name of a present custom/standard fragment
            before (str|datetime):  Only operations before this date
            after (str|datetime):  Only operations after this date
            date_from (str|datetime):  Same as `after`
            date_to (str|datetime):  Same as `before`
            min_age (timedelta|str):  Minimum age for selected operations
            max_age (timedelta|str):  Maximum age for selected operations
            asc (bool):  Return results in ascending (oldest first) order if True,
                descending (newest first) if False. None (default) uses the
                server default (ascending for Operations).
            revert (bool): Reverse the default ordering.
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
            AsyncIterator of Operation objects
        """
        # Operations server default = ascending. asc=False means revert=True
        if revert is None and asc is not None:
            revert = not asc
        page_size = resolve_page_size(page_size, limit, include, exclude)
        params = (
            map_params(
                fragment=fragment,
                bulk_id=bulk_id,
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                revert=revert,
                page_size=page_size,
                agentId=agent_id,
                deviceId=device_id,
                status=status,
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
            preserve_order=(asc is not None) or (revert is not None) or expression_implies_order(expression),
        )

    async def get_all(
        self,
        expression: str | None = None,
        *,
        agent_id: str | None = None,
        device_id: str | None = None,
        status: str | None = None,
        bulk_id: str | None = None,
        fragment: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        asc: bool | None = None,
        revert: bool | None = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[Operation]:
        """Query the database for operations and return the results as list.

        See `select` for a documentation of arguments.

        Returns:
            List of matching Operation objects
        """
        return [
            x
            async for x in self.select(
                expression=expression,
                agent_id=agent_id,
                device_id=device_id,
                status=status,
                bulk_id=bulk_id,
                fragment=fragment,
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                asc=asc,
                revert=revert,
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

    async def get_last(
        self,
        expression: str | None = None,
        *,
        agent_id: str | None = None,
        device_id: str | None = None,
        status: str | None = None,
        bulk_id: str | None = None,
        fragment: str | None = None,
        date_to: str | datetime | None = None,
        before: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        **kwargs,
    ) -> Operation | None:
        """Query the database and return the last matching operation.

        Returns:
            Last matching Operation object or None
        """
        params = (
            map_params(
                fragment=fragment,
                bulk_id=bulk_id,
                before=before,
                date_to=date_to,
                min_age=min_age,
                revert=True,  # forces use of date constraint
                page_size=1,
                agentId=agent_id,
                deviceId=device_id,
                status=status,
                **kwargs,
            )
            if not expression
            else ()
        )
        return await self._get_last(expression=expression, params=params, as_values=as_values)

    async def get_count(
        self,
        expression: str | None = None,
        *,
        agent_id: str | None = None,
        device_id: str | None = None,
        status: str | None = None,
        bulk_id: str | None = None,
        fragment: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        **kwargs,
    ) -> int:
        """Calculate the number of potential results of a database query.

        Returns:
            Number of potential results
        """
        params = (
            map_params(
                fragment=fragment,
                bulk_id=bulk_id,
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                page_size=1,
                agentId=agent_id,
                deviceId=device_id,
                status=status,
                **kwargs,
            )
            if not expression
            else ()
        )
        return await self._get_count(expression=expression, params=params)

    async def delete_by(
        self,
        expression: str | None = None,
        *,
        agent_id: str | None = None,
        device_id: str | None = None,
        status: str | None = None,
        bulk_id: str | None = None,
        fragment: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        **kwargs,
    ) -> None:
        """Query the database and delete matching operations.

        Args:
            expression (str):  Arbitrary filter expression; all other filters
                are ignored if this is provided
            agent_id (str):  Database ID of agent
            device_id (str):  Database ID of device
            status (str):  Operation status
            bulk_id (str):  Bulk operation ID
            fragment (str):  Name of a present custom fragment
            before (str|datetime):  Only operations before this date
            after (str|datetime):  Only operations after this date
            min_age (timedelta|str):  Minimum age
            max_age (timedelta|str):  Maximum age
        """
        if expression:
            await self.c8y.delete(f"{self.resource_path}?{expression}")
        else:
            params = map_params(
                fragment=fragment,
                bulk_id=bulk_id,
                before=before,
                after=after,
                min_age=min_age,
                max_age=max_age,
                agentId=agent_id,
                deviceId=device_id,
                status=status,
                **kwargs,
            )
            await self.c8y.delete(self.resource_path, params=params)

    async def create(self, *operations: Operation, workers: int | None = None) -> None:
        """Create operation objects within the database.

        Args:
            *operations (Operation):  Collection of Operation instances
            workers (int):  Number of parallel workers
        """
        await self._create(*operations, workers=workers)

    async def update(self, *operations: Operation, workers: int | None = None) -> None:
        """Update operation objects within the database.

        Args:
            *operations (Operation):  Collection of Operation instances
            workers (int):  Number of parallel workers
        """
        await self._update(*operations, workers=workers)


class BulkOperationStatus(StrEnum):
    """Bulk Operation statuses."""

    ACTIVE = "ACTIVE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DELETED = "DELETED"


class BulkOperationGeneralStatus(StrEnum):
    """Bulk Operation general statuses."""

    SCHEDULED = "PENDING"
    EXECUTING = "EXECUTING"
    EXECUTING_WITH_ERRORS = "EXECUTING_WITH_ERRORS"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    COMPLETED_SUCCESSFULLY = "COMPLETED SUCCESSFULLY"
    COMPLETED_WITH_FAILURES = "COMPLETED WITH FAILURES"


class BulkOperation(WithId, CumulocityObject):
    """Represents an instance of a bulk operation object in Cumulocity.

    Instances of this class are returned by functions of the corresponding
    Bulk Operation API. Use this class to create new or update existing
    bulk operations.

    See also: https://cumulocity.com/api/core/#tag/Bulk-operations
    """

    _meta = BulkOperationMeta

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        *,
        group_id: str | None = None,
        failed_parent_id: str | None = None,
        start_time: str | datetime | None = None,
        creation_ramp: float | None = None,
        operation_prototype: dict | None = None,
        **kwargs,
    ):
        super().__init__(c8y, **kwargs)
        self.group_id = group_id
        self.failed_parent_id = failed_parent_id
        self.start_time = start_time
        self.creation_ramp = creation_ramp
        if operation_prototype is not None:
            self._staged_json["operationPrototype"] = operation_prototype

    group_id = json_property("groupId")
    failed_parent_id = json_property("failedParentId")
    start_time = time_property("startDate")
    start_datetime = datetime_property("startDate")
    creation_ramp = json_property("creationRamp")
    status = json_property("status", read_only=True)
    general_status = json_property("generalStatus", read_only=True)
    operation_prototype = json_property("operationPrototype")

    async def create(self, copy: bool = False) -> Self:
        """Store the Bulk Operation within the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The created BulkOperation. By default, this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._create(copy)

    async def update(self, copy: bool = False) -> Self:
        """Update the BulkOperation within the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated BulkOperation. By default, this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._update(copy)

    async def reload(self, copy: bool = False) -> Self:
        """Reload the BulkOperation from the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The reloaded BulkOperation. By default, this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._reload(copy)


class BulkOperations(CumulocityResource[BulkOperation]):
    """Provides access to the Bulk Operations API.

    This class can be used for get, search for, create, update and
    delete bulk operations within the Cumulocity database.

    See also: https://cumulocity.com/api/core/#tag/Bulk-operations
    """

    _meta = BulkOperationMeta
    _object_type = BulkOperation

    async def get(self, operation_id: str) -> BulkOperation:
        """Read a specific bulk operation from the database.

        Args:
            operation_id (str):  Database ID of the bulk operation

        Returns:
            BulkOperation object
        """
        return await self._get(operation_id)

    def select(
        self,
        expression: str | None = None,
        *,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[BulkOperation]:
        """Query the database for bulk operations and iterate over the results.

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided
            include (str|JsonMatcher):  Client-side inclusion filter
            exclude (str|JsonMatcher):  Client-side exclusion filter
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int):  Pull a specific page only
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of BulkOperation objects
        """
        page_size = resolve_page_size(page_size, limit, include, exclude)
        params = map_params(page_size=page_size, **kwargs) if not expression else ()
        return self._iterate(
            expression=expression,
            params=params,
            page_number=page_number,
            limit=limit,
            include=include,
            exclude=exclude,
            workers=workers,
            preserve_order=False,
        )

    async def get_all(
        self,
        expression: str | None = None,
        *,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[BulkOperation]:
        """Query the database for bulk operations and return the results as list.

        See `select` for a documentation of arguments.

        Returns:
            List of BulkOperation objects
        """
        return [
            x
            async for x in self.select(
                expression=expression,
                include=include,
                exclude=exclude,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                workers=workers,
                **kwargs,
            )
        ]

    async def get_count(self, expression: str | None = None, **kwargs) -> int:
        """Calculate the number of potential results of a database query.

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided

        Returns:
            Number of potential results
        """
        params = map_params(page_size=1, **kwargs) if not expression else ()
        return await self._get_count(expression=expression, params=params)

    async def create(self, *operations: BulkOperation, workers: int | None = None) -> None:
        """Create bulk operation objects within the database.

        Args:
            *operations (BulkOperation):  Collection of BulkOperation instances
            workers (int):  Number of parallel workers
        """
        await self._create(*operations, workers=workers)

    async def update(self, *operations: BulkOperation, workers: int | None = None) -> None:
        """Update bulk operation objects within the database.

        Args:
            *operations (BulkOperation):  Collection of BulkOperation instances
            workers (int):  Number of parallel workers
        """
        await self._update(*operations, workers=workers)
