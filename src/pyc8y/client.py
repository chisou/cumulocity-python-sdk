# Copyright (c) 2026 Christoph Souris

from typing import Awaitable, Callable

import aiohttp

from pyc8y.auth import Auth
from pyc8y.model.alarm import Alarms
from pyc8y.model.application import Applications
from pyc8y.model.audit import AuditRecords
from pyc8y.model.binary import Binaries
from pyc8y.model.event import Events
from pyc8y.model.identity import Identity
from pyc8y.model.inventory import Inventory, DeviceInventory, DeviceGroupInventory
from pyc8y.model.measurement import Measurements
from pyc8y.model.notification2 import Subscriptions, Tokens
from pyc8y.model.operation import Operations, BulkOperations
from pyc8y.model.tenant_option import TenantOptions
from pyc8y.model.tenants import Tenants
from pyc8y.model.user import Users, UserGroups, InventoryRoles
from pyc8y.rest import CumulocityRestClient


class CumulocityClient(CumulocityRestClient):
    """Main Cumulocity client.

    Provides usage-centric access to a Cumulocity instance.
    """

    def __init__(
        self,
        base_url: str,
        tenant_id: str,
        auth: Auth,
        application_key: str = None,
        processing_mode: str = None,
        connector_factory: Callable[[], Awaitable[aiohttp.BaseConnector]] | None = None,
    ):
        super().__init__(
            base_url, tenant_id, auth, application_key, processing_mode,
            connector_factory=connector_factory,
        )
        self.alarms = Alarms(self)
        self.applications = Applications(self)
        self.audit_records = AuditRecords(self)
        self.binaries = Binaries(self)
        self.bulk_operations = BulkOperations(self)
        self.events = Events(self)
        self.identity = Identity(self)
        self.inventory = Inventory(self)
        self.device_inventory = DeviceInventory(self)
        self.group_inventory = DeviceGroupInventory(self)
        self.measurements = Measurements(self)
        self.operations = Operations(self)
        self.subscriptions = Subscriptions(self)
        self.tenant_options = TenantOptions(self)
        self.tenants = Tenants(self)
        self.tokens = Tokens(self)
        self.inventory_roles = InventoryRoles(self)
        self.user_groups = UserGroups(self)
        self.users = Users(self)
