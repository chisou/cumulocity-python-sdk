# Copyright (c) 2025 Cumulocity GmbH

import asyncio

from dotenv import load_dotenv

from pyc8y.app import SimpleCumulocityApp


async def main():
    load_dotenv()
    c8y = SimpleCumulocityApp()
    print("CumulocityApp initialized.")
    print(f"{c8y.base_url}, Tenant: {c8y.tenant_id}, User:{c8y.username}")

    try:
        value1 = await c8y.tenant_options.get_value(category='remoteaccess', key='credentials.encryption.password')
        print(f"Value: {value1}")
    except KeyError:
        print("Unable to read encrypted tenant option.")


asyncio.run(main())
