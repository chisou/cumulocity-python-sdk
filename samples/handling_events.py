# Copyright (c) 2025 Cumulocity GmbH

import asyncio
import logging

from dotenv import load_dotenv
from inputimeout import inputimeout, TimeoutOccurred

from pyc8y.app import SimpleCumulocityApp
from pyc8y.model import Device, Event

logging.basicConfig(level=logging.DEBUG)


async def main():
    load_dotenv()  # load environment from a .env if present
    c8y = SimpleCumulocityApp()
    print("CumulocityApp initialized.")
    print(f"{c8y.base_url}, Tenant: {c8y.tenant_id}, User:{c8y.username}")

    # Creating a new (digital only) device to play with
    new_device = await Device(c8y, type='test_SomeDevice', name='MyTestDevice', custom_fragment={'foo': 'bar'},
                              com_cumulocity_model_Agent={}).create()
    print(f"\nCreated new device: {new_device.name} #{new_device.id}")

    # Creating a new event
    event = await Event(c8y, type='text_SomeEvent', time='now', source=new_device.id,
                        text='Something happened').create()
    print(f"\nCreated event: {event.type} #{event.id}, JSON: {event.to_full_json()}"
          f"\nLink: {c8y.base_url}/apps/devicemanagement/index.html#/device/{new_device.id}/events")

    # Adding a custom fragment
    event['test_AdditionalFragment'] = {'foo': 'bar'}
    print(f"\nUpdate JSON: {event.to_diff_json()}")
    event = await event.update()

    # Adding an attachment
    response = await event.create_attachment('./cumulocity.json', content_type='text/plain')
    print(f"\nAttached binary: {response}")

    # Cleaning up
    print("\n\nCleanup:\n")

    wait_time = 60
    try:
        inputimeout(f"Press ENTER to continue. (Timeout: {wait_time}s)", timeout=wait_time)
    except TimeoutOccurred:
        pass

    await new_device.delete()
    print('\nDevice removed.')


asyncio.run(main())
