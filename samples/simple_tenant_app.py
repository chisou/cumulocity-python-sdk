# Copyright (c) 2025 Cumulocity GmbH

from __future__ import annotations

import asyncio

from dotenv import load_dotenv
from inputimeout import inputimeout, TimeoutOccurred

from pyc8y.app import SimpleCumulocityApp
from pyc8y.model import Celsius, Device, Measurement, Operation


# A simple (per tenant) Cumulocity application can be created just like this.
# The authentication information is read from the standard Cumulocity
# environment variables that are injected into the Docker container.


async def main():
    load_dotenv()  # load environment from a .env if present
    c8y = SimpleCumulocityApp()
    print("CumulocityApp initialized.")
    print(f"{c8y.base_url}, Tenant: {c8y.tenant_id}, User:{c8y.username}")

    # The SimpleCumulocityApp behaves just like any other CumulocityApi instance,
    # e.g. ...

    # Reading users:
    print("\nRegistered users:")
    async for u in c8y.users.select():
        print(f"  {u.username}, {u.id}")

    # Reading devices:
    print("\nDevices:")
    async for d in c8y.device_inventory.select(page_size=100):
        print(f"  {d.name} #{d.id}")

    # Creating devices
    new_device = await Device(c8y, type='test_SomeDevice', name='MyTestDevice', custom_fragment={'foo': 'bar'},
                              com_cumulocity_model_Agent={}).create()
    print(f"\nCreated new device: {new_device.name} #{new_device.id}")

    # Creating Measurements
    print("\nMeasurements:")
    for v in range(0, 10):
        m = await Measurement(c8y, type='test_SomeMeasurementType', source=new_device.id,
                              c8y_TemperatureMeasurement={'t': Celsius(v)}).create()
        print(f"  Created measurement: #{m.id}, JSON: {m.to_full_json()}")

    # Creating Operation
    print("\nOperation")
    new_operation = Operation(c8y, device_id=new_device.id, description='Shell command',
                              c8y_Command={'text': 'myCommand'})
    await new_operation.create()

    operation_list = await c8y.operations.get_all(agent_id=new_device.id, status='PENDING', page_size=1)
    pending_operation = operation_list[0]
    print(pending_operation.status)

    pending_operation.status = 'EXECUTING'
    await pending_operation.update()

    # Cleaning up
    print("\n\nCleanup:\n\n")

    wait_time = 300  # seconds
    try:
        inputimeout(f"Press ENTER to continue. (Timeout: {wait_time}s)", timeout=wait_time)
    except TimeoutOccurred:
        pass

    # Removing measurements
    await c8y.measurements.delete_by(source=new_device.id)
    print('\nMeasurements removed.')

    await new_device.delete()
    print('\nDevice removed.')


asyncio.run(main())
