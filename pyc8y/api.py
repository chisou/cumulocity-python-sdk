from pyc8y.auth import Auth
from pyc8y.base import CumulocityRestApi
from pyc8y.model import Alarms


class CumulocityApi(CumulocityRestApi):
    """Main Cumulocity App.

    Provides usage centric access to a Cumulocity instance.
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