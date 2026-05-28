from datetime import datetime, timedelta
from typing import AsyncIterator, Self, Sequence

from pyc8y.rest import CumulocityRestClient
from pyc8y.model.model_base import (
    CumulocityObject,
    CumulocityResource,
    WithId,
    json_property,
    datetime_property,
    expression_implies_order,
    id_property,
    time_property,
    map_params,
    resolve_page_size,
)
from pyc8y.model.matcher import JsonMatcher
from pyc8y.types import EventMeta, FileSpec


class Event(WithId, CumulocityObject):
    """Represent an instance of an event object in Cumulocity.

    Instances of this class are returned by functions of the corresponding
    Events API. Use this class to create new or update Event objects.

    See also: https://cumulocity.com/api/#tag/Events
    """

    _meta = EventMeta

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        type: str | None = None,  # noqa (type)
        time: str | datetime | None = None,
        source: str | None = None,
        text: str | None = None,
        **kwargs,
    ):
        super().__init__(c8y, **kwargs)
        self.type = type
        self.source = source
        self.time = time
        self.text = text

    type = json_property("type")
    source = id_property("source")
    text = json_property("text")
    time = time_property("time")
    datetime = datetime_property("time")
    creation_time = json_property("creationTime", read_only=True)
    creation_datetime = datetime_property("creationTime")
    update_time = json_property("lastUpdated", read_only=True)
    update_datetime = datetime_property("lastUpdated")
    last_updated = json_property("lastUpdated", read_only=True)
    last_updated_datetime = datetime_property("lastUpdated")

    @property
    def attachment_path(self) -> str:
        return f"{self.object_path}/binaries"

    def has_attachment(self) -> bool:
        """Check whether the event has a binary attachment.

        Event objects that have an attachment feature a `c8y_IsBinary`
        fragment. This function checks the presence of that fragment.

        Note: This does not query the database. Hence, the information might
        be outdated if a binary was attached _after_ the event object was
        last read from the database.

        Returns:
            True if the event object has an attachment, False otherwise.
        """
        return self.has("c8y_IsBinary")

    async def create_attachment(self, file: FileSpec, content_type: str | None = None) -> dict:
        """Create the binary attachment.

        Args:
            file (str | PathLike | BinaryIO): File-like object or a file path
            content_type (str):  Content type of the file sent
                (default is application/octet-stream)

        Returns:
            Attachment details as JSON object (dict).
        """
        self._assert_c8y()
        self._assert_key()
        return await self.c8y.post_file(self.attachment_path, file=file, content_type=content_type)

    async def update_attachment(self, file: FileSpec, content_type: str | None = None) -> dict:
        """Update the binary attachment.

        Args:
            file (str | PathLike | BinaryIO): File-like object or a file path
            content_type (str):  Content type of the file sent
                (default is application/octet-stream)

        Returns:
            Attachment details as JSON object (dict).
        """
        self._assert_c8y()
        self._assert_key()
        return await self.c8y.put_file(self.attachment_path, file=file, content_type=content_type)

    async def download_attachment(self) -> bytes:
        """Read the binary attachment.

        Returns:
            The event's binary attachment as bytes.
        """
        self._assert_c8y()
        self._assert_key()
        return await self.c8y.get_file(self.attachment_path)

    async def delete_attachment(self) -> None:
        """Remove the binary attachment."""
        self._assert_c8y()
        self._assert_key()
        await self.c8y.delete(self.attachment_path)

    async def create(self) -> Self:
        """Create this event within the database.

        Returns:
            A fresh Event instance representing what was created (including the ID).
        """
        return await self._create()

    async def update(self, copy: bool = False) -> Self:
        """Write changes to this event to the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated Event. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._update(copy)

    async def delete(self, **_) -> None:
        """Delete this event from the database."""
        await self._delete()

    async def reload(self, copy: bool = False) -> Self:
        """Reload this event's data from the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The reloaded Event. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._reload(copy)

    async def apply_to(self, other_id: str) -> Self:
        """Apply changes made to this event to another event in the database.

        Args:
            other_id (str):  Database ID of the event to update.

        Returns:
            A fresh Event instance representing the updated state.
        """
        return await self._apply_to(other_id)


class Events(CumulocityResource[Event]):
    """Provides access to the Events API.

    This class can be used for get, search for, create, update and
    delete events within the Cumulocity database.

    See also: https://cumulocity.com/api/core/#tag/Events
    """

    _meta = EventMeta
    _object_type = Event

    def build_attachment_path(self, event_id: str) -> str:
        """Build the attachment path of a specific event.

        Args:
            event_id (str):  Database ID of the event

        Returns:
            The relative path to the event attachment within Cumulocity.
        """
        return f"{self.build_object_path(event_id)}/binaries"

    async def get(self, event_id: str) -> Event:  # noqa (id)
        """Retrieve a specific event from the database.

        Args:
            event_id (str):  The database ID of the event

        Returns:
            An Event instance representing the object in the database.
        """
        return await self._get(event_id)

    def select(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,  # noqa (type)
        source: str | None = None,
        fragment: str | None = None,
        fragment_type: str | None = None,
        fragment_value: str | None = None,
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
        with_source_assets: bool | None = None,
        with_source_devices: bool | None = None,
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
    ) -> AsyncIterator[Event]:
        """Query the database for events and iterate over the results.

        This function is implemented in a lazy fashion - results will only be
        fetched from the database as long there is a consumer for them.

        All parameters are considered to be filters, limiting the result set
        to objects which meet the filter's specification.  Filters can be
        combined (within reason).

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            type (str):  Event type
            source (str):  Database ID of a source device
            fragment (str):  Name of a present custom/standard fragment
            fragment_type (str):  Type of a present custom/standard fragment
            fragment_value (str):  Value of a present custom/standard fragment
            before (str|datetime):  Datetime object or ISO date/time string. Only
                events assigned to a time before this date are returned.
            after (str|datetime):  Datetime object or ISO date/time string. Only
                events assigned to a time after this date are returned.
            date_from (str|datetime): Same as `after`
            date_to (str|datetime): Same as `before`
            min_age (timedelta): Minimum age for selected events.
            max_age (timedelta): Maximum age for selected events.
            created_before (str|datetime):  Only events created before this date are returned.
            created_after (str|datetime):  Only events created after this date are returned.
            created_from (str|datetime): Same as `created_after`
            created_to (str|datetime): Same as `created_before`
            updated_before (str|datetime):  Only events updated before this date are returned.
            updated_after (str|datetime):  Only events updated after this date are returned.
            last_updated_from (str|datetime): Same as `updated_after`
            last_updated_to (str|datetime): Same as `updated_before`
            with_source_assets (bool): Whether also events for related source
                assets should be included. Requires `source`.
            with_source_devices (bool): Whether also events for related source
                devices should be included. Requires `source`.
            asc (bool): Return results in ascending (oldest first) order if True,
                descending (newest first) if False. None (default) lets the
                server apply its default order (descending for Events).
            revert (bool): Reverse the default ordering.
            limit (int | None):  Maximum number of results; pass `None` to fetch all.
            include (str|JsonMatcher): Client-side inclusion filter.
            exclude (str|JsonMatcher): Client-side exclusion filter.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int): Pull a specific page only.
            as_values: Extract values at JSON paths as tuples.
            workers (int): Number of parallel page-fetch workers.

        Returns:
            AsyncIterator of Event objects
        """
        # Events server default = descending. asc=True means revert=True
        if revert is None and asc is not None:
            revert = asc
        page_size = resolve_page_size(page_size, limit, include, exclude)
        params = (
            map_params(
                type=type,
                source=source,
                fragment=fragment,
                fragment_type=fragment_type,
                fragment_value=fragment_value,
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
                with_source_assets=with_source_assets,
                with_source_devices=with_source_devices,
                revert=revert,
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
            preserve_order=(asc is not None) or (revert is not None) or expression_implies_order(expression),
        )

    async def get_all(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,  # noqa (type)
        source: str | None = None,
        fragment: str | None = None,
        fragment_type: str | None = None,
        fragment_value: str | None = None,
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
        with_source_assets: bool | None = None,
        with_source_devices: bool | None = None,
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
    ) -> list[Event]:
        """Query the database for events and return the results as list.

        This function is a greedy version of the `select` function. All
        available results are read immediately and returned as list.

        See `select` for a documentation of arguments.

        Returns:
            List of Event objects
        """
        return [
            x
            async for x in self.select(
                expression=expression,
                type=type,
                source=source,
                fragment=fragment,
                fragment_type=fragment_type,
                fragment_value=fragment_value,
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
                with_source_assets=with_source_assets,
                with_source_devices=with_source_devices,
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

    async def get_count(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,  # noqa (type)
        source: str | None = None,
        fragment: str | None = None,
        fragment_type: str | None = None,
        fragment_value: str | None = None,
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
                fragment=fragment,
                fragment_type=fragment_type,
                fragment_value=fragment_value,
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
                **kwargs,
            )
            if not expression
            else ()
        )
        return await self._get_count(expression=expression, params=params)

    async def get_last(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,  # noqa (type)
        source: str | None = None,
        fragment: str | None = None,
        fragment_type: str | None = None,
        fragment_value: str | None = None,
        before: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        with_source_assets: bool | None = None,
        with_source_devices: bool | None = None,
        **kwargs,
    ) -> Event | None:
        """Retrieve the most recent matching event.

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            type (str):  Event type
            source (str):  Database ID of a source device
            fragment (str):  Name of a present custom/standard fragment
            fragment_type (str):  Type of a present custom/standard fragment
            fragment_value (str):  Value of a present custom/standard fragment
            before (str|datetime):  Upper time bound
            date_to (str|datetime): Same as `before`
            min_age (timedelta): Minimum age for selected events.
            with_source_assets (bool): Whether to include events for related assets.
            with_source_devices (bool): Whether to include events for related devices.

        Returns:
            The most recent Event, or None if no match is found.
        """
        # ensure a lower bound so the query returns results ordered newest-first
        after = None if (before or date_to or min_age) else "1970-01-01"
        params = (
            map_params(
                type=type,
                source=source,
                fragment=fragment,
                fragment_type=fragment_type,
                fragment_value=fragment_value,
                before=before,
                after=after,
                date_to=date_to,
                min_age=min_age,
                with_source_assets=with_source_assets,
                with_source_devices=with_source_devices,
                **kwargs,
            )
            if not expression
            else ()
        )
        return await self._get_last(expression=expression, params=params)

    async def create(self, *events: Event, workers: int | None = None) -> None:
        """Create event objects within the database.

        Args:
            *events (Event):  Collection of Event instances
            workers (int):  Number of parallel workers
        """
        await self._create(*events, workers=workers)

    async def update(self, *events: Event, workers: int | None = None) -> None:
        """Write changes to the database.

        Args:
            *events (Event):  Collection of Event instances
            workers (int):  Number of parallel workers
        """
        await self._update(*events, workers=workers)

    async def delete(self, *events: str | Event, workers: int | None = None) -> None:
        """Delete event objects from the database.

        Args:
            *events (str | Event):  Collection of Event instances or IDs
            workers (int):  Number of parallel workers
        """
        await self._delete(*events, workers=workers)

    async def apply_to(self, model: dict | Event, *event_ids: str, workers: int | None = None) -> None:
        """Apply a model event (or dict) to a set of existing events.

        Args:
            model (dict | Event):  Template event or dict with changes to apply
            *event_ids (str):  Database IDs of events to update
            workers (int):  Number of parallel workers
        """
        await self._apply_to(model, *event_ids, workers=workers)

    async def delete_by(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,  # noqa (type)
        source: str | None = None,
        fragment: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        **kwargs,
    ) -> None:
        """Query the database and delete matching events.

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            type (str):  Event type
            source (str):  Database ID of a source device
            fragment (str):  Name of a present custom/standard fragment
            before (str|datetime):  Only events before this date are deleted.
            after (str|datetime):  Only events after this date are deleted.
            date_from (str|datetime): Same as `after`
            date_to (str|datetime): Same as `before`
            min_age (timedelta): Minimum age for selected events.
            max_age (timedelta): Maximum age for selected events.
        """
        if expression:
            await self.c8y.delete(f"{self.resource_path}?{expression}")
            return
        params = map_params(
            type=type,
            source=source,
            fragment=fragment,
            before=before,
            after=after,
            date_from=date_from,
            date_to=date_to,
            min_age=min_age,
            max_age=max_age,
            **kwargs,
        )
        await self.c8y.delete(self.resource_path, params=params)

    async def create_attachment(self, event_id: str, file: FileSpec, content_type: str | None = None) -> dict:
        """Add a binary attachment to an event.

        Args:
            event_id (str):  The database ID of the event
            file (str | PathLike | BinaryIO): File-like object or a file path
            content_type (str):  Content type of the file sent

        Returns:
            Attachment details as JSON object (dict).
        """
        return await self.c8y.post_file(self.build_attachment_path(event_id), file=file, content_type=content_type)

    async def update_attachment(self, event_id: str, file: FileSpec, content_type: str | None = None) -> dict:
        """Update a binary attachment of an event.

        Args:
            event_id (str):  The database ID of the event
            file (str | PathLike | BinaryIO): File-like object or a file path
            content_type (str):  Content type of the file sent

        Returns:
            Attachment details as JSON object (dict).
        """
        return await self.c8y.put_file(self.build_attachment_path(event_id), file=file, content_type=content_type)

    async def download_attachment(self, event_id: str) -> bytes:
        """Read a binary attachment of an event.

        Args:
            event_id (str):  The database ID of the event

        Returns:
            The event's binary attachment as bytes.
        """
        return await self.c8y.get_file(self.build_attachment_path(event_id))

    async def delete_attachment(self, event_id: str) -> None:
        """Remove a binary attachment from an event.

        Args:
            event_id (str):  The database ID of the event
        """
        await self.c8y.delete(self.build_attachment_path(event_id))
