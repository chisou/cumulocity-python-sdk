"""Smoke test run against the built wheel/sdist in CI.

Verifies that the installed package is importable and exposes its
documented top-level surface — catches packaging mistakes (missing
modules, wrong package layout, broken __init__) before publishing.
"""

import pyc8y
from pyc8y import (
    CumulocityClient,
    CumulocityRestClient,
    DeviceRegistryClient,
    MultiTenantCumulocityApp,
    SimpleCumulocityApp,
    get_client,
)
from pyc8y.model import (
    Alarm,
    Alarms,
    Event,
    Events,
    Measurement,
    Measurements,
)
from pyc8y.notification2 import Listener, QueueListener

print(f"pyc8y {pyc8y.__name__} smoke test OK")
