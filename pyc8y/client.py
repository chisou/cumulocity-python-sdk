# Copyright (c) 2026 Christoph Souris

from pyc8y.auth import Auth
from pyc8y.model.alarm import Alarms
from pyc8y.model.application import Applications
from pyc8y.model.event import Events
from pyc8y.model.inventory import Inventory, DeviceInventory, DeviceGroupInventory
from pyc8y.model.measurement import Measurements
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
            processing_mode: str = None
    ):
        super().__init__(base_url, tenant_id, auth, application_key, processing_mode)
        self.alarms = Alarms(self)
        self.applications = Applications(self)
        self.events = Events(self)
        self.inventory = Inventory(self)
        self.device_inventory = DeviceInventory(self)
        self.group_inventory = DeviceGroupInventory(self)
        self.measurements = Measurements(self)
