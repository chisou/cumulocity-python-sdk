# Copyright (c) 2025 Cumulocity GmbH

# pylint: disable=missing-function-docstring

import asyncio

from pyc8y.app import SimpleCumulocityApp
from pyc8y.model import ManagedObject, Subscription
from pyc8y.notification2 import QueueListener

from util.testing_util import create_random_name, load_dotenv


async def main():
    c8y = SimpleCumulocityApp()
    print("CumulocityApp initialized.")
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

    # Create a queue-based listener for the previously created subscription.
    # Messages are pushed into an asyncio.Queue and consumed from a separate task.
    listener = QueueListener(
        c8y,
        subscription_name=sub.name,
        auto_unsubscribe=True,
    )

    async def consume():
        while True:
            msg = await listener.queue.get()
            print(f"Received message, ID: {msg.id}, Source: {msg.source}, Action: {msg.action}, Body: {msg.json}")

    # Start listening and consuming
    listener.start()
    consumer_task = asyncio.create_task(consume())

    # Some action: Update the managed object
    await asyncio.sleep(5)
    mo['cx_CustomFragment'] = {'num': 42}
    await mo.update()

    # The update event is now being processed
    await asyncio.sleep(5)

    # Stop the listener and the consumer
    listener.stop()
    await listener.wait()
    consumer_task.cancel()

    # cleanup subscription and managed object
    await sub.delete()
    await mo.delete()


# load environment from a .env if present
load_dotenv()
# run main coroutine
asyncio.run(main())
