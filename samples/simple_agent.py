# Copyright (c) 2025 Cumulocity GmbH

import asyncio
import os
import uuid

import dotenv

from pyc8y.auth import BasicAuth
from pyc8y.client import CumulocityClient
from pyc8y.model import Device, Event
from pyc8y.registry import DeviceRegistryClient

# Usually, each Cumulocity device agent has its own access credentials which
# are created by Cumulocity during the device registration process.
# This sample simulates this using a Cumulocity device registry connection.
#
# See also: https://cumulocity.com/guides/users-guide/device-management/#connecting-devices
#
# The authentication information is read from the environment. Please provide
# the environment variables mentioned below (a .env file is accepted as well).


async def main():
    dotenv.load_dotenv()
    base_url = os.environ['C8Y_BASEURL']
    bootstrap_tenant = 'management'
    bootstrap_username = os.environ['C8Y_DEVICEBOOTSTRAP_USER']
    bootstrap_password = os.environ['C8Y_DEVICEBOOTSTRAP_PASSWORD']

    device_serial = f'pyc8y-{uuid.uuid1()}'

    print(f"Generated device serial: {device_serial}"
          "\nPlease open the Cumulocity UI and register a device for this serial.")
    input("\nPress ENTER to continue.")

    # The device registry is a special version of the Cumulocity API,
    # it should be used using device bootstrap credentials.
    c8y_registry = DeviceRegistryClient(
        base_url=base_url,
        tenant_id=bootstrap_tenant,
        auth=BasicAuth(f"{bootstrap_tenant}/{bootstrap_username}", bootstrap_password),
    )

    print("\nThis client will now continuously query for the device credentials."
          "\nPlease approve the request within the Cumulocity UI.")
    # The registry blocks until the device registration was acknowledged
    # and returns a Credentials object that can then be used to construct
    # a device-specific connection.
    async with c8y_registry:
        creds = await c8y_registry.await_credentials(device_serial)

    c8y_device = CumulocityClient(
        base_url=base_url,
        tenant_id=creds.tenant_id,
        auth=BasicAuth(f"{creds.tenant_id}/{creds.username}", creds.password),
    )
    print(f"Device registration successful. Username: {c8y_device.username}")

    async with c8y_device:
        # The device connection is then used to define the device's digital twin
        # within the Cumulocity database:
        device = await Device(c8y_device, type='sag_PythonDevice', name='Sample Python Device').create()
        print(f"Digital twin created. Database ID: {device.id}")

        # It is recommended to register the external ID as a serial as well:
        await c8y_device.identity.create(
            external_id=device_serial,
            external_type='c8y_Serial',
            managed_object_id=device.id,
        )
        print("External ID created.")

        # We now send a simple event from the device
        await Event(c8y_device, type='sag_PythonInitDone', source=device.id, time='now',
                    text='Device initialization done.').create()

        # Cleaning up
        input("\nPress ENTER to continue to cleanup.")

        print("\nCleanup:\n")

        # Removing the external ID
        await c8y_device.identity.delete(external_id=device_serial, external_type='c8y_Serial')
        print("External ID removed.")

        # Removing the device (also removes the device user)
        await device.delete(with_device_user=True)
        print("Digital twin removed (including user).")


asyncio.run(main())
