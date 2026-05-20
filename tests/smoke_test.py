# ruff: noqa: F401  -- imports themselves are the test
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

assert pyc8y.__version__ and pyc8y.__version__ != "0.0.0+unknown", (
    f"unexpected version: {pyc8y.__version__!r}"
)
print(f"pyc8y {pyc8y.__version__} smoke test OK")
