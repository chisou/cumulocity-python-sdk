# Copyright (c) 2026 Christoph Souris

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version(__name__)
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

from pyc8y.app import (
    SimpleCumulocityApp as SimpleCumulocityApp,
    MultiTenantCumulocityApp as MultiTenantCumulocityApp,
    get_client as get_client,
)
from pyc8y.client import CumulocityClient as CumulocityClient
from pyc8y.registry import DeviceRegistryClient as DeviceRegistryClient
from pyc8y.rest import (
    AccessDeniedError as AccessDeniedError,
    BatchError as BatchError,
    CumulocityRestClient as CumulocityRestClient,
    HttpError as HttpError,
    MissingTfaError as MissingTfaError,
    UnauthorizedError as UnauthorizedError,
)
