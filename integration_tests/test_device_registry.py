# Copyright (c) 2026 Christoph Souris

# pylint: disable=redefined-outer-name

import asyncio
import os
import time
from collections.abc import AsyncGenerator
from datetime import datetime

import pytest

from pyc8y.auth import BasicAuth
from pyc8y.client import CumulocityClient
from pyc8y.model import Device
from pyc8y.registry import DeviceRegistryClient

from util.testing_util import create_random_name


@pytest.fixture(scope="session")
async def device_registry(test_environment, logger) -> AsyncGenerator[DeviceRegistryClient, None]:
    """Provide a device registry instance."""
    try:
        base_url = os.environ["C8Y_BASEURL"]
        bootstrap_tenant = os.environ["C8Y_DEVICEBOOTSTRAP_TENANT"]
        bootstrap_user = os.environ["C8Y_DEVICEBOOTSTRAP_USER"]
        bootstrap_password = os.environ["C8Y_DEVICEBOOTSTRAP_PASSWORD"]
    except KeyError as e:
        raise RuntimeError(
            f"Missing Cumulocity environment variable: {e} "
            "Please define the required variables directly or setup a .env file."
        ) from e

    auth = BasicAuth(username=f"{bootstrap_tenant}/{bootstrap_user}", password=bootstrap_password)
    client = DeviceRegistryClient(base_url=base_url, tenant_id=bootstrap_tenant, auth=auth)
    yield client
    await client.close()



@pytest.fixture(scope="function")
async def sample_device(live_c8y: CumulocityClient, device_registry: DeviceRegistryClient, logger) -> AsyncGenerator[Device, None]:
    """Provide a sample device, created via the device registry process."""

    device_id = create_random_name()

    # 1) create a device connection request
    await live_c8y.device_inventory.request(device_id)

    # 2) continuously try to accept the request in the background;
    # it can be accepted once there was some communication
    async def await_communication_and_accept():
        # pylint: disable=bare-except
        for _ in range(100):
            try:
                await live_c8y.device_inventory.accept(device_id)
                break
            except:
                logger.info("Unable to accept device request. Waiting for device communication.")
                await asyncio.sleep(0.5)

    asyncio.create_task(await_communication_and_accept())

    # 3) wait for the request acceptance and retrieve device-specific credentials
    logger.info(f"Requesting credentials for device '{device_id}'.")
    credentials = await device_registry.await_credentials(device_id)
    logger.info("Credentials request accepted.")

    device_c8y = CumulocityClient(
        base_url=device_registry.base_url,
        tenant_id=credentials.tenant_id,
        auth=BasicAuth(
            username=f"{credentials.tenant_id}/{credentials.username}",
            password=credentials.password,
        ),
    )

    # 4) create a digital twin
    device = await Device(c8y=device_c8y, name=device_id, type="c8y_TestDevice").create()
    logger.info(f"Device created: '{device_id}', ID: {device.id}, Owner: {device.owner}")

    yield device

    logger.info("Deleting the device (and user) ...")
    await device.delete()
    logger.info(f"Device '{device_id}' deleted.")
    await live_c8y.users.delete(device.owner)
    logger.info(f"User '{device.owner}' deleted.")


async def test_device_created(sample_device: Device):
    """Verify that the sample device was created properly."""

    # -> should have a database ID
    assert sample_device.id

    # -> should have been created less than 10s before
    now = time.time()
    creation_time = datetime.timestamp(sample_device.creation_datetime)
    assert creation_time - now < 10

    # -> should have a proper device user as owner
    assert sample_device.owner == sample_device.c8y.username
    assert sample_device.owner == sample_device.get_username()