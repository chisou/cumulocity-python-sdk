# Copyright (c) 2026 Christoph Souris

from abc import ABC
from datetime import datetime, timedelta
from enum import StrEnum
from typing import ClassVar, Sequence, Any, TypedDict

from c8y_api.model import JsonMatcher

IdSpec = str | None
ParamsSpec = Sequence[tuple[str, str]] | None
AsValuesSpec = str | tuple[str, Any] | Sequence[str | tuple[str, Any]] | None
MatcherSpec = str | JsonMatcher | None
DatetimeSpec = str | datetime | None
TimedeltaSpec = str | timedelta | None

class MimeType(StrEnum):
    ALARM = "application/vnd.com.nsn.cumulocity.alarm+json"
    ALARM_COLLECTION = "application/vnd.com.nsn.cumulocity.alarmcollection+json"
    APPLICATION = "application/vnd.com.nsn.cumulocity.application+json"
    APPLICATION_COLLECTION = "application/vnd.com.nsn.cumulocity.applicationcollection+json"
    AUDIT_RECORD = "application/vnd.com.nsn.cumulocity.auditrecord+json"
    CURRENT_USER = "application/vnd.com.nsn.cumulocity.currentuser+json"
    EVENT = "application/vnd.com.nsn.cumulocity.event+json"
    EVENT_COLLECTION = "application/vnd.com.nsn.cumulocity.eventcollection+json"
    GLOBAL_ROLE = "application/vnd.com.nsn.cumulocity.group+json"
    MANAGED_OBJECT = "application/vnd.com.nsn.cumulocity.managedobject+json"
    MANAGED_OBJECT_COLLECTION = "application/vnd.com.nsn.cumulocity.managedobjectcollection+json"
    MEASUREMENT = "application/vnd.com.nsn.cumulocity.measurement+json"
    MEASUREMENT_COLLECTION = "application/vnd.com.nsn.cumulocity.measurementcollection+json"
    USER = "application/vnd.com.nsn.cumulocity.user+json"


class ResourceMeta(ABC):
    object_mime_type: ClassVar[str]
    collection_mime_type: ClassVar[str]
    resource_path: ClassVar[str]
    collection_name: ClassVar[str]

    @classmethod
    def build_object_path(cls, object_id):
        return f"{cls.resource_path}/{object_id}"


class MeasurementsMeta(ResourceMeta):
    object_mime_type = MimeType.MEASUREMENT
    collection_mime_type = MimeType.MEASUREMENT_COLLECTION
    resource_path = "measurement/measurements"
    collection_name = "measurements"


class EventsMeta(ResourceMeta):
    object_mime_type = MimeType.EVENT
    collection_mime_type = MimeType.EVENT_COLLECTION
    resource_path = "event/events"
    collection_name = "events"


class AlarmMeta(ResourceMeta):
    object_mime_type = MimeType.ALARM
    collection_mime_type = MimeType.ALARM_COLLECTION
    resource_path = "alarm/alarms"
    collection_name = "alarms"


class ApplicationsMeta(ResourceMeta):
    object_mime_type = MimeType.APPLICATION
    collection_mime_type = MimeType.APPLICATION_COLLECTION
    resource_path = "application/applications"
    collection_name = "applications"


class InventoryMeta(ResourceMeta):
    object_mime_type = MimeType.MANAGED_OBJECT
    collection_mime_type = MimeType.MANAGED_OBJECT_COLLECTION
    resource_path = "inventory/managedObjects"
    collection_name = "managedObjects"


class InventoryFilter(TypedDict, total=False):
    """Filter parameters for inventory queries.

    Attributes:
        query (str):  Complex query to execute; all other filters are
            ignored if such a custom query is provided
        ids (List[str|int]): Specific object ID to select.
        order_by (str):  Field/expression to sort the results.
        type (str):  Object type
        parent (str):  Parent object in the asset hierarchy (ID).
        fragment (str):  Name of a present custom/standard fragment
        fragments (list[str]): Additional fragments present within objects
        name (str):  Name of the object
            Note: The Cumulocity REST API does not support filtering for
            names directly; this is a convenience parameter which will
            translate all filters into a query string.
        owner (str):  Username of the object owner
        text (str): Text value of any object property.
    """
    query: str
    ids: list[str | int]
    type: str
    parent: str
    fragment: str
    fragments: list[str]
    name: str
    owner: str
    text: str


class InventorySelectFilter(InventoryFilter, total=False):
    """Filter parameters for inventory select queries.

    Attributes:
        only_roots (bool): Whether to include only objects that don't have
            any parent
        with_children (bool):  Whether children with ID and name should be
            included with each returned object
        with_children_count (bool): When set to true, the returned result
            will contain the total number of children in the respective
            child additions, assets and devices sub fragments.
        skip_children_names (bool):  If true, returned references of child
            devices won't contain their names.
        with_groups (bool): Whether to include additional information about
            the groups to which the searched object belongs to.
            This results in setting the assetParents property with
            additional information about the groups.
        with_parents (bool): Whether to include a device's parents.
        with_latest_values (bool):  If true the platform includes the
            fragment `c8y_LatestMeasurements, which contains the latest
            measurement values reported by the device to the platform.
    """
    order_by: str
    only_roots: bool
    with_children: bool
    with_children_count: bool
    skip_children_names: bool
    with_groups: bool
    with_parents: bool
    with_latest_values: bool
