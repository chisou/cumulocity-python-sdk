# Copyright (c) 2025 Cumulocity GmbH

# pylint: disable=missing-function-docstring

import asyncio

from pyc8y.app import SimpleCumulocityApp
from pyc8y.model import ManagedObject, Subscription
from pyc8y.notification2 import Listener
from pyc8y.rest import ProcessingMode

from util.testing_util import create_random_name, load_dotenv


async def main():
    # initialize Cumulocity connection(s)
    c8y = SimpleCumulocityApp()  # PERSISTENT
    c8y_transient = SimpleCumulocityApp(processing_mode=ProcessingMode.TRANSIENT)
    c8y_quiescent = SimpleCumulocityApp(processing_mode=ProcessingMode.QUIESCENT)

    print("CumulocityApp(s) initialized.")
    print(f"{c8y.base_url}, Tenant: {c8y.tenant_id}, User:{c8y.username}")

    # Create a managed object to play with
    mo_name = create_random_name(3)
    mo = await ManagedObject(c8y, name=mo_name, type='c8y_CustomType').create()
    print(f"Managed object created: #{mo.id} '{mo_name}'")

    # Create a subscription to listen for updates on
    # previously created managed object
    sub_name = f'{mo_name.replace("_", "")}Subscription'
    sub = await Subscription(c8y, name=sub_name, context=Subscription.Context.MANAGED_OBJECT,
                             source_id=mo.id).create()
    print(f"Subscription created: {sub_name}")

    # Create a listener for previously created subscription
    listener = Listener(c8y, subscription_name=sub.name)

    # Define callback function.
    async def callback(msg):
        print(f"Received message, ID: {msg.id}, Source: {msg.source}, Action: {msg.action}, Body: {msg.json}")

    # Start listening
    listener.start(callback)

    # Some action: Update the managed object (persistent)
    await asyncio.sleep(5)
    mo['cx_CustomFragment'] = {'num': 42}
    print("Updated managed object (persistent).")
    await mo.update()

    await asyncio.sleep(1)
    mo_transient = await c8y_transient.inventory.get(mo.id)
    print(f"Managed Object fragments: {mo_transient.fragments}")
    mo_transient['cx_Transient'] = {'num': 42}
    print("Updated managed object (transient).")
    await mo_transient.update()

    await asyncio.sleep(1)
    mo_quiescent = await c8y_quiescent.inventory.get(mo.id)
    print(f"Managed Object fragments: {mo_quiescent.fragments}")
    mo_quiescent['cx_Quiescent'] = {'num': 42}
    print("Updated managed object (quiescent).")
    await mo_quiescent.update()

    await asyncio.sleep(1)
    final_mo = await c8y.inventory.get(mo.id)
    print(f"Final Managed Object fragments: {final_mo.fragments}")

    # The update event is now being processed
    await asyncio.sleep(5)

    # close the listener
    listener.stop()
    await listener.wait()

    # cleanup subscription and managed object
    await sub.delete()
    await mo.delete()


# load environment from a .env if present
load_dotenv()
# run main coroutine
asyncio.run(main())
