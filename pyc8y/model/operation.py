# Copyright (c) 2026 Christoph Souris

from datetime import datetime, timedelta
from enum import StrEnum
from typing import AsyncIterator, Any, Self

from pyc8y.base_util import flatten
from pyc8y.rest import CumulocityRestClient
from pyc8y.model.inventory import Device
from pyc8y.model.matcher import JsonMatcher
from pyc8y.model.model_base import (
    CumulocityObject,
    CumulocityResource,
    json_property,
    datetime_property,
    time_property,
    map_params,
    run_batched,
    ensure_ids,
)
from pyc8y.types import OperationMeta, BulkOperationMeta, AsValuesSpec


class OperationStatus(StrEnum):
    """Operation statuses."""

    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"


class Operation(CumulocityObject):
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

    device_id = json_property("deviceId")
    description = json_property("description")
    status = json_property("status")
    creation_time = json_property("creationTime", read_only=True)
    creation_datetime = datetime_property("creationTime")

    async def create(self) -> Self:
        """Store the Operation within the database.

        Returns:
            A fresh Operation object representing what was created within the database.
        """
        return await self._create()

    async def update(self) -> Self:
        """Update the Operation within the database.

        Returns:
            A fresh Operation object representing the updated state.
        """
        return await self._update()

    async def send_to(self, *devices: str | Device, workers: int | None = None) -> None:
        """Send the Operation to devices within the database.

        Args:
            *devices (str | Device): A collection of devices or device IDs
            workers (int): The number of parallel processes to use
        """
        self._assert_c8y()
        skip_keys = {"creationTime", "delivery", "id", "self", "status", "deviceId", "deviceName"}
        operation_json = {k: v for k, v in self.to_json(only_updated=False).items() if k not in skip_keys}
        await run_batched(
            ensure_ids(flatten(devices)),
            workers,
            lambda x: self.c8y.post(self.resource_path, operation_json | {"deviceId": x}, accept=None),
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
        reverse: bool = False,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = None,
        page_size: int = 1000,
        page_number: int | None = None,
        as_values: AsValuesSpec | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[Operation | Any | tuple[Any]]:
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
            reverse (bool):  Invert the order of results
            include (str|JsonMatcher):  Client-side inclusion filter
            exclude (str|JsonMatcher):  Client-side exclusion filter
            limit (int):  Limit the number of results
            page_size (int):  Number of records read per request
            page_number (int):  Pull a specific page only
            as_values:  Extract values at JSON paths as tuples
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of Operation objects
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
                reverse=reverse,
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
        reverse: bool = False,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = None,
        page_size: int = 1000,
        page_number: int | None = None,
        as_values: AsValuesSpec | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[Operation | Any | tuple[Any]]:
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
        as_values: AsValuesSpec | None = None,
        **kwargs,
    ) -> Operation | None:
        """Query the database and return the last matching operation.

        Returns:
            Last matching Operation object or None
        """
        after = None
        if not before and not min_age:
            after = "1970-01-01"
        params = (
            map_params(
                fragment=fragment,
                bulk_id=bulk_id,
                after=after,
                before=before,
                date_to=date_to,
                min_age=min_age,
                reverse=True,
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


class BulkStatus(StrEnum):
    """Bulk Operation statuses."""

    ACTIVE = "ACTIVE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DELETED = "DELETED"


class GeneralBulkStatus(StrEnum):
    """Bulk Operation general statuses."""

    SCHEDULED = "PENDING"
    EXECUTING = "EXECUTING"
    EXECUTING_WITH_ERRORS = "EXECUTING_WITH_ERRORS"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    COMPLETED_SUCCESSFULLY = "COMPLETED SUCCESSFULLY"
    COMPLETED_WITH_FAILURES = "COMPLETED WITH FAILURES"


class BulkOperation(CumulocityObject):
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

    async def create(self) -> Self:
        """Store the Bulk Operation within the database.

        Returns:
            A fresh BulkOperation object representing what was created within the database.
        """
        return await self._create()

    async def update(self) -> Self:
        """Update the BulkOperation within the database.

        Returns:
            A fresh BulkOperation object representing the updated state.
        """
        return await self._update()

    async def reload(self) -> Self:
        """Reload the BulkOperation from the database."""
        return await self._reload()


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
        *,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = None,
        page_size: int = 1000,
        page_number: int | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[BulkOperation | Any | tuple[Any]]:
        """Query the database for bulk operations and iterate over the results.

        Args:
            include (str|JsonMatcher):  Client-side inclusion filter
            exclude (str|JsonMatcher):  Client-side exclusion filter
            limit (int):  Limit the number of results
            page_size (int):  Number of records read per request
            page_number (int):  Pull a specific page only
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of BulkOperation objects
        """
        params = map_params(page_size=page_size, **kwargs)
        return self._iterate(
            params=params,
            page_number=page_number,
            limit=limit,
            include=include,
            exclude=exclude,
            workers=workers,
        )

    async def get_all(
        self,
        *,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = None,
        page_size: int = 1000,
        page_number: int | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[BulkOperation | Any | tuple[Any]]:
        """Query the database for bulk operations and return the results as list.

        See `select` for a documentation of arguments.

        Returns:
            List of BulkOperation objects
        """
        return [
            x
            async for x in self.select(
                include=include,
                exclude=exclude,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                workers=workers,
                **kwargs,
            )
        ]

    async def get_count(self, **kwargs) -> int:
        """Calculate the number of potential results of a database query.

        Returns:
            Number of potential results
        """
        params = map_params(page_size=1, **kwargs)
        return await self._get_count(expression=None, params=params)
