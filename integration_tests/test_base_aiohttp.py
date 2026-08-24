import asyncio
import os

import dotenv

from pyc8y.rest import CumulocityRestClient
from pyc8y.auth import BasicAuth


def test(benchmark):
    dotenv.load_dotenv()

    async def run():
        async with CumulocityRestClient(
                base_url=os.environ["C8Y_BASEURL"],
                tenant_id=os.environ["C8Y_TENANT"],
                auth=BasicAuth(
                    os.environ["C8Y_USER"],
                    os.environ["C8Y_PASSWORD"]),
        ) as c8y:
            await c8y.get("/inventory/managedObjects?pageSize=100")

    loop = asyncio.new_event_loop()
    try:
        benchmark(lambda: loop.run_until_complete(run()))
    finally:
        loop.close()
