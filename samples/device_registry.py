# Copyright (c) 2025 Cumulocity GmbH
# pylint: disable=broad-except

import asyncio
import logging

import dotenv

from pyc8y.auth import BasicAuth
from pyc8y.client import CumulocityClient
from pyc8y.model import Device, Event
from pyc8y.registry import DeviceRegistryClient


DEVICE_ID = 'BengalBonobo18'


async def main():
    # load environment from a .env file
    env = dotenv.dotenv_values()
    c8y_baseurl = env['C8Y_BASEURL']
    c8y_tenant = env['C8Y_TENANT']
    c8y_user = env['C8Y_USER']
    c8y_password = env['C8Y_PASSWORD']
    bootstrap_tenant = env['C8Y_DEVICEBOOTSTRAP_TENANT']
    bootstrap_user = env['C8Y_DEVICEBOOTSTRAP_USER']
    bootstrap_password = env['C8Y_DEVICEBOOTSTRAP_PASSWORD']

    logger = logging.getLogger('com.cumulocity.test.device_registry')
    logging.basicConfig()
    logger.setLevel('INFO')

    # a regular Cumulocity connection to create/approve device requests and such
    c8y = CumulocityClient(
        base_url=c8y_baseurl,
        tenant_id=c8y_tenant,
        auth=BasicAuth(f"{c8y_tenant}/{c8y_user}", c8y_password),
    )
    # a special Cumulocity 'device registry' client to get device credentials
    registry = DeviceRegistryClient(
        base_url=c8y_baseurl,
        tenant_id=bootstrap_tenant,
        auth=BasicAuth(f"{bootstrap_tenant}/{bootstrap_user}", bootstrap_password),
    )

    async with c8y, registry:
        # 1) create device request
        await c8y.device_inventory.request(DEVICE_ID)
        logger.info(f"Device '{DEVICE_ID}' requested. Approve in Cumulocity now.")

        # 2) await device credentials (approval within Cumulocity)
        device_c8y = None
        try:
            creds = await registry.await_credentials(DEVICE_ID, timeout='5h', pause='5s')
            device_c8y = CumulocityClient(
                base_url=c8y_baseurl,
                tenant_id=creds.tenant_id,
                auth=BasicAuth(f"{creds.tenant_id}/{creds.username}", creds.password),
            )
        except Exception as e:
            logger.error("Got error", exc_info=e)
            return

        async with device_c8y:
            # 3) Create a digital twin
            device = await Device(c8y=device_c8y, name=DEVICE_ID, type='c8y_TestDevice',
                                  c8y_RequiredAvailability={"responseInterval": 10}).create()
            logger.info(f"Device created: '{device.name}', ID: {device.id}, Owner:{device.owner}")

            # 4) send an event
            await Event(c8y=device_c8y, type='c8y_TestEvent', time='now',
                        source=device.id, text="Test event").create()

            # 5) check device's availability status
            try:
                availability = await c8y.get(f'/inventory/managedObjects/{device.id}/availability')
                logger.info(f"Device availability: {availability}")
            except KeyError:
                logger.error("Device availability not defined!")

            # 6) cleanup device
            await device.delete()
            logger.info(f"Device '{DEVICE_ID}' deleted.")
            await c8y.users.delete(device.owner)
            logger.info(f"User '{device.owner}' deleted.")


asyncio.run(main())
