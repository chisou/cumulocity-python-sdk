from datetime import datetime, timedelta
from enum import StrEnum
from typing import AsyncGenerator, TypedDict, Unpack

from pyc8y.base import CumulocityRestApi
from pyc8y.model.base import CumulocityObject, json_property, datetime_property, id_property, CumulocityResource, \
    assert_c8y, map_params


class Severity(StrEnum):
    """Alarm severity levels."""
    MAJOR = 'MAJOR'
    CRITICAL = 'CRITICAL'
    MINOR = 'MINOR'
    WARNING = 'WARNING'


class Status:
    """Alarm statuses."""
    ACTIVE = 'ACTIVE'
    ACKNOWLEDGED = 'ACKNOWLEDGED'
    CLEARED = 'CLEARED'


class Alarm(CumulocityObject):
    """Represent an instance of an event object in Cumulocity.

    Instances of this class are returned by functions of the corresponding
    Events API. Use this class to create new or update Event objects.

    See also: https://cumulocity.com/api/#tag/Events
    """

    _c8y_resource = "/alarm/alarms/"
    _c8y_object_name = "Alarm"
    _c8y_mime_type = "application/json"  # todo: fix?

    def __init__(
            self,
            c8y: CumulocityRestApi = None,
            type: str = None,   # noqa (type)
            time: str | datetime = None,
            source: str = None,
            text: str = None,
            status: str = None,
            severity: Severity | str = None,
            **kwargs
    ):
        super().__init__(c8y, **kwargs)
        self.type = type
        self.source = source
        self.time = time
        self.text = text
        self.status = status
        self.severity = Severity(severity)

    type = json_property("type")
    source = id_property("source")
    text = json_property("text")
    time = json_property("time")
    status = json_property("status")
    severity = json_property("severity")
    datetime = datetime_property("datetime")
    creation_time = json_property("creationTime", read_only=True)
    creation_datetime = datetime_property("creationTime")
    update_time = json_property("lastUpdated", read_only=True)
    update_datetime = datetime_property("lastUpdated")
    last_updated = json_property("lastUpdated", read_only=True)
    last_updated_datetime = datetime_property("lastUpdated")

    def delete(self, **_) -> None:
        """Delete this object within the database.

        An alarm is identified through its type and source. These fields
        must be defined for this to function. This is always the case if
        the instance was built by the API.

        See also functions `Alarms.delete` and `Alarms.delete_by`
        """
        assert_c8y(self)
        if not self.type:
            raise ValueError("The alarm type must be set to allow unambiguous identification.")
        if not self.source:
            raise ValueError("The alarm source must be set to allow unambiguous identification.")
        # Alarms(self.c8y).delete_by(type=self.type, source=self.source)


class _BaseParams(TypedDict, total=False):
    limit: int
    page_number: int
    as_values: str | tuple | list[str | tuple]

class _MeaParams(TypedDict):
    type: str
    source: str

class _TimeParams(TypedDict):
    before: str | datetime
    after: str | datetime
    date_from: str | datetime
    date_to: str | datetime
    min_age: str | timedelta
    max_age: str | timedelta

class _UpdateParams(TypedDict):
    updated_before: str | datetime
    updated_after: str | datetime
    last_updated_from: str | datetime
    last_updated_to: str | datetime

class _CreateParams(TypedDict):
    created_before: str | datetime
    created_after: str | datetime
    created_from: str | datetime
    created_to: str | datetime

class _OrderParams(TypedDict):
    reverse: bool
    revert: bool

class _QueryParams(TypedDict):
    q: str
    query: str
    filter: str

# class _MatcherParams(TypedDict):
#     include: str | JsonMatcher
#     exclude: str | JsonMatcher




class Alarms(CumulocityResource[Alarm]):
    _c8y_type = Alarm
    object_name = "Alarm"
    resource_path = "/alarm/alarms"
    object_mime_type = "application/vnd.com.nsn.cumulocity.alarm+json"
    collection_mime_type = "application/vnd.com.nsn.cumulocity.alarmcollection+json"

    def select(
            self,
            expression: str = None,
            type: str = None,
            source: str = None,
            status: str = None,
            resolved: str = None,
            severity: str = None,
            fragment: str = None,
            with_source_assets: bool = None,
            with_source_devices: bool = None,
            before: str | datetime = None,
            after: str | datetime = None,
            date_from: str | datetime = None,
            date_to: str | datetime = None,
            created_before: str | datetime = None,
            created_after: str | datetime = None,
            created_from: str | datetime = None,
            created_to: str | datetime = None,
            updated_before: str | datetime = None,
            updated_after: str | datetime = None,
            last_updated_from: str | datetime = None,
            last_updated_to: str | datetime = None,
            min_age: str | timedelta = None,
            max_age: str | timedelta = None,
            reverse: bool = False,
            revert: bool = False,
            # include: str | JsonMatcher = None,
            # exclude: str | JsonMatcher = None,
            limit: int = None,
            page_size: int = 100,
            page_number: int = None,
            as_values: str | tuple | list[str | tuple] = None,
           **kwargs
    ) -> AsyncGenerator[Alarm, None]:
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
            created_before (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time before this date are returned.
            created_after (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time after this date are returned.
            updated_before (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time before this date are returned.
            updated_after (str|datetime):  Datetime object or ISO date/time string.
                Only alarms changed at a time after this date are returned.
            min_age (timedelta):  Matches only alarms of at least this age
            max_age (timedelta):  Matches only alarms with at most this age
            date_from (str|datetime): Same as `after`
            date_to (str|datetime): Same as `before`
            created_from (str|datetime): Same as `created_after`
            created_to(str|datetime): Same as `created_before`
            last_updated_from (str|datetime): Same as `updated_after`
            last_updated_to (str|datetime): Same as `updated_before`
            with_source_assets (bool): Whether also alarms for related source
                assets should be included. Requires `source`.
            with_source_devices (bool): Whether also alarms for related source
                devices should be included. Requires `source`
            reverse (bool):  Invert the order of results, starting with the
                most recent one
            revert(bool):  Same as`reverse`
            limit (int): Limit the number of results to this number.
            include (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The inclusion is applied first.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            exclude (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The exclusion is applied second.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            page_size (int): Define the number of alarms which are read (and
                parsed in one chunk). This is a performance related setting.
            page_number (int): Pull a specific page; this effectively disables
                automatic follow-up page retrieval.
            as_values: (*str|tuple):  Don't parse objects, but directly extract
                the values at certain JSON paths as tuples; If the path is not
                defined in a result, None is used; Specify a tuple to define
                a proper default value for each path.

        Returns:
            Generator of Alarm objects

        See also:
            https://github.com/bytebutcher/pydfql/blob/main/docs/USER_GUIDE.md#4-query-language
        """
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
            with_source_devices=with_source_devices,
            with_source_assets=with_source_assets,
            reverse=reverse,
            revert=revert,
            page_size=page_size,
            **kwargs
        ) if not expression else {}
        return self._iterate(expression=expression, params=params, limit=limit, page_number=page_number)

    async def get_all(
            self,

            expression: str = None,
            type: str = None,
            source: str = None,
            status: str = None,
            resolved: str = None,
            severity: str = None,
            fragment: str = None,
            with_source_assets: bool = None,
            with_source_devices: bool = None,
            before: str | datetime = None,
            after: str | datetime = None,
            date_from: str | datetime = None,
            date_to: str | datetime = None,
            created_before: str | datetime = None,
            created_after: str | datetime = None,
            created_from: str | datetime = None,
            created_to: str | datetime = None,
            updated_before: str | datetime = None,
            updated_after: str | datetime = None,
            last_updated_from: str | datetime = None,
            last_updated_to: str | datetime = None,
            min_age: str | timedelta = None,
            max_age: str | timedelta = None,
            reverse: bool = False,
            revert: bool = False,
            # include: str | JsonMatcher = None,
            # exclude: str | JsonMatcher = None,
            limit: int = None,
            page_size: int = 100,
            page_number: int = None,
            as_values: str | tuple | list[str | tuple] = None,
            **kwargs
    ) -> list[Alarm]:
        """Query the database for alarms and return the results as list.

        This function is a greedy version of the select function. All
        available results are read immediately and returned as list.

        See `select` for a documentation of arguments.

        Returns:
            List of Alarm objects
        """
        return list(x async for x in self.select(
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
            reverse=reverse,
            revert=revert,
            with_source_devices=with_source_devices,
            with_source_assets=with_source_assets,
            limit=limit,
            # include=include, exclude=exclude,
            page_size=page_size,
            page_number=page_number,
            as_values=as_values,
            **kwargs))