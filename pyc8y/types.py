from abc import ABC
from typing import ClassVar


class MimeType:
    MANAGED_OBJECT = "application/vnd.com.nsn.cumulocity.managedobject+json"
    MANAGED_OBJECT_COLLECTION = "application/vnd.com.nsn.cumulocity.managedobjectcollection+json"
    USER = 'application/vnd.com.nsn.cumulocity.user+json'
    CURRENT_USER = 'application/vnd.com.nsn.cumulocity.currentuser+json'
    GLOBAL_ROLE = 'application/vnd.com.nsn.cumulocity.group+json'
    AUDIT_RECORD = 'application/vnd.com.nsn.cumulocity.auditrecord+json'
    MEASUREMENT = "application/vnd.com.nsn.cumulocity.measurement+json"
    MEASUREMENT_COLLECTION = 'application/vnd.com.nsn.cumulocity.measurementcollection+json'
    EVENT = "application/vnd.com.nsn.cumulocity.event+json"
    EVENT_COLLECTION = "application/vnd.com.nsn.cumulocity.eventcollection+json"


class ResourceMeta(ABC):
    object_mime_type: ClassVar[str]
    collection_mime_type: ClassVar[str]
    resource_path: ClassVar[str]
    collection_name: ClassVar[str]

    @classmethod
    def build_object_path(cls, object_id):
        return f"{cls.resource_path}/{object_id}"


class MeasurementsMeta(ABC):
    object_mime_type = MimeType.MEASUREMENT
    collection_mime_type = MimeType.MEASUREMENT_COLLECTION
    resource_path = "measurement/measurements"
    collection_name = "measurements"


class EventsMeta(ABC):
    object_mime_type = MimeType.EVENT
    collection_mime_type = MimeType.EVENT_COLLECTION
    resource_path = "event/events"
    collection_name = "events"


class InventoryMeta(ResourceMeta):
    object_mime_type = MimeType.MANAGED_OBJECT
    collection_mime_type = MimeType.MANAGED_OBJECT_COLLECTION
    resource_path = "inventory/managedObjects"
    collection_name = "managedObjects"

