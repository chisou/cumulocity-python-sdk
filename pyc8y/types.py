# Copyright (c) 2026 Christoph Souris

from abc import ABC
from datetime import datetime, timedelta
from enum import StrEnum
from typing import ClassVar, Sequence, Any

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

