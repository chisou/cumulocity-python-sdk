# Copyright (c) 2026 Christoph Souris

import os
from abc import ABC
from enum import StrEnum
from typing import BinaryIO, ClassVar, Sequence, Any

AsValuesSpec = str | tuple[str, Any] | Sequence[str | tuple[str, Any]]

FileSpec = str | os.PathLike | BinaryIO
"""File-like object or a file path."""

DEFAULT_PAGE_SIZE = 100
"""Default page size used by paged queries when neither `page_size` nor `limit` constrain it."""


class MimeType(StrEnum):
    ALARM = "application/vnd.com.nsn.cumulocity.alarm+json"
    ALARM_COLLECTION = "application/vnd.com.nsn.cumulocity.alarmcollection+json"
    APPLICATION = "application/vnd.com.nsn.cumulocity.application+json"
    APPLICATION_COLLECTION = "application/vnd.com.nsn.cumulocity.applicationcollection+json"
    APPLICATION_USER_COLLECTION = "application / vnd.com.nsn.cumulocity.applicationusercollection+json"
    AUDIT_RECORD = "application/vnd.com.nsn.cumulocity.auditrecord+json"
    AUDIT_RECORD_COLLECTION = "application/vnd.com.nsn.cumulocity.auditrecordcollection+json"
    BULK_OPERATION = "application/vnd.com.nsn.cumulocity.bulkoperation+json"
    BULK_OPERATION_COLLECTION = "application/vnd.com.nsn.cumulocity.bulkoperationcollection+json"
    CURRENT_USER = "application/vnd.com.nsn.cumulocity.currentuser+json"
    EVENT = "application/vnd.com.nsn.cumulocity.event+json"
    EVENT_COLLECTION = "application/vnd.com.nsn.cumulocity.eventcollection+json"
    EXTERNAL_ID = ("application/vnd.com.nsn.cumulocity.externalid+json",)
    GLOBAL_ROLE = "application/vnd.com.nsn.cumulocity.group+json"
    INVENTORY_ROLE = "application/vnd.com.nsn.cumulocity.inventoryrole+json"
    INVENTORY_ROLE_COLLECTION = "application/vnd.com.nsn.cumulocity.inventoryrolecollection+json"
    MANAGED_OBJECT = "application/vnd.com.nsn.cumulocity.managedobject+json"
    MANAGED_OBJECT_COLLECTION = "application/vnd.com.nsn.cumulocity.managedobjectcollection+json"
    MEASUREMENT = "application/vnd.com.nsn.cumulocity.measurement+json"
    MEASUREMENT_COLLECTION = "application/vnd.com.nsn.cumulocity.measurementcollection+json"
    OPERATION = "application/vnd.com.nsn.cumulocity.operation+json"
    OPERATION_COLLECTION = "application/vnd.com.nsn.cumulocity.operationcollection+json"
    SUBSCRIPTION = "application/vnd.com.nsn.cumulocity.subscription+json"
    SUBSCRIPTION_COLLECTION = "application/vnd.com.nsn.cumulocity.subscriptioncollection+json"
    TENANT = "application/vnd.com.nsn.cumulocity.tenant+json"
    TENANT_COLLECTION = "application/vnd.com.nsn.cumulocity.tenantcollection+json"
    TENANT_OPTION = "application/vnd.com.nsn.cumulocity.option+json"
    TENANT_OPTION_COLLECTION = "application/vnd.com.nsn.cumulocity.optionCollection+json"
    USER = "application/vnd.com.nsn.cumulocity.user+json"
    USER_COLLECTION = "application/vnd.com.nsn.cumulocity.usercollection+json"
    USER_GROUP = "application/vnd.com.nsn.cumulocity.group+json"
    USER_GROUP_COLLECTION = "application/vnd.com.nsn.cumulocity.groupcollection+json"
    TENANT_USAGE_STATISTICS_COLLECTION = "application/vnd.com.nsn.cumulocity.tenantusagestatisticscollection+json"
    TENANT_USAGE_STATISTICS_SUMMARY = "application/vnd.com.nsn.cumulocity.tenantusagestatisticssummary+json"
    TENANT_USAGE_STATISTICS_SUMMARY_ALL_TENANTS = "application/json"
    TENANT_STATISTICS_DATE = "application/vnd.com.nsn.cumulocity.tenantstatisticsdate+json"
    TENANT_STATISTICS_FILE = "application/vnd.com.nsn.cumulocity.tenantstatisticsfile+json"
    TENANT_STATISTICS_FILE_COLLECTION = "application/vnd.com.nsn.cumulocity.tenantStatisticsfilecollection + json"


class ResourceMeta(ABC):
    object_mime_type: ClassVar[str]
    collection_mime_type: ClassVar[str]
    resource_path: ClassVar[str]
    collection_name: ClassVar[str]

    @classmethod
    def build_object_path(cls, object_id):
        return f"{cls.resource_path}/{object_id}"


class AlarmMeta(ResourceMeta):
    object_mime_type = MimeType.ALARM
    collection_mime_type = MimeType.ALARM_COLLECTION
    resource_path = "alarm/alarms"
    collection_name = "alarms"


class ApplicationMeta(ResourceMeta):
    object_mime_type = MimeType.APPLICATION
    collection_mime_type = MimeType.APPLICATION_COLLECTION
    resource_path = "application/applications"
    collection_name = "applications"


class AuditRecordMeta(ResourceMeta):
    object_mime_type = MimeType.AUDIT_RECORD
    collection_mime_type = MimeType.AUDIT_RECORD_COLLECTION
    resource_path = "audit/auditRecords"
    collection_name = "auditRecords"


class BinaryMeta(ResourceMeta):
    object_mime_type = MimeType.MANAGED_OBJECT
    collection_mime_type = MimeType.MANAGED_OBJECT_COLLECTION
    resource_path = "inventory/binaries"
    collection_name = "managedObjects"


class BulkOperationMeta(ResourceMeta):
    object_mime_type = MimeType.BULK_OPERATION
    collection_mime_type = MimeType.BULK_OPERATION_COLLECTION
    resource_path = "devicecontrol/bulkoperations"
    collection_name = "bulkOperations"


class EventMeta(ResourceMeta):
    object_mime_type = MimeType.EVENT
    collection_mime_type = MimeType.EVENT_COLLECTION
    resource_path = "event/events"
    collection_name = "events"


class IdentityMeta(ResourceMeta):
    object_mime_type = MimeType.EXTERNAL_ID
    collection_mime_type = MimeType.EXTERNAL_ID
    collection_name = "externalIds"

    @classmethod
    def build_object_path(cls, _) -> str:
        raise NotImplementedError("Function not available for Identity API.")


class InventoryMeta(ResourceMeta):
    object_mime_type = MimeType.MANAGED_OBJECT
    collection_mime_type = MimeType.MANAGED_OBJECT_COLLECTION
    resource_path = "inventory/managedObjects"
    collection_name = "managedObjects"


class MeasurementMeta(ResourceMeta):
    object_mime_type = MimeType.MEASUREMENT
    collection_mime_type = MimeType.MEASUREMENT_COLLECTION
    resource_path = "measurement/measurements"
    collection_name = "measurements"


class OperationMeta(ResourceMeta):
    object_mime_type = MimeType.OPERATION
    collection_mime_type = MimeType.OPERATION_COLLECTION
    resource_path = "devicecontrol/operations"
    collection_name = "operations"


class SubscriptionMeta(ResourceMeta):
    object_mime_type = MimeType.SUBSCRIPTION
    collection_mime_type = MimeType.SUBSCRIPTION_COLLECTION
    resource_path = "notification2/subscriptions"
    collection_name = "subscriptions"


class TenantOptionMeta(ResourceMeta):
    object_mime_type = MimeType.TENANT_OPTION
    collection_mime_type = MimeType.TENANT_OPTION_COLLECTION
    resource_path = "tenant/options"
    collection_name = "options"


class TenantMeta(ResourceMeta):
    object_mime_type = MimeType.TENANT
    collection_mime_type = MimeType.TENANT_COLLECTION
    resource_path = "tenant/tenants"
    collection_name = "tenants"


class TenantDeviceStatisticsMeta(ResourceMeta):
    object_mime_type = "application/json"
    collection_mime_type = "application/json"
    resource_path = "tenant/statistics/devices"
    collection_name = "statistics"


class TenantUsageStatisticsMeta(ResourceMeta):
    object_mime_type = None
    collection_mime_type = MimeType.TENANT_USAGE_STATISTICS_COLLECTION
    resource_path = "tenant/statistics"
    collection_name = "usageStatistics"


class TenantStatisticsFilesMeta(ResourceMeta):
    object_mime_type = MimeType.TENANT_STATISTICS_FILE
    collection_mime_type = MimeType.TENANT_STATISTICS_FILE_COLLECTION
    resource_path = "tenant/statistics/files"
    collection_name = "statisticsFiles"


class InventoryRoleMeta(ResourceMeta):
    object_mime_type = MimeType.INVENTORY_ROLE
    collection_mime_type = MimeType.INVENTORY_ROLE_COLLECTION
    resource_path = "user/inventoryroles"
    collection_name = "roles"


class UserGroupMeta(ResourceMeta):
    object_mime_type = MimeType.USER_GROUP
    collection_mime_type = MimeType.USER_GROUP_COLLECTION
    collection_name = "groups"


class UserMeta(ResourceMeta):
    object_mime_type = MimeType.USER
    collection_mime_type = MimeType.USER_COLLECTION
    collection_name = "users"

    @classmethod
    def build_object_path(cls, _) -> str:
        raise NotImplementedError("Function not available for User API.")


class CurrentUserMeta(ResourceMeta):
    object_mime_type = MimeType.CURRENT_USER
    collection_mime_type = None
    collection_name = None

    @classmethod
    def build_object_path(cls, _) -> str:
        raise NotImplementedError("Function not available for CurrentUser API.")
