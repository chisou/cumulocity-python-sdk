import asyncio
import os

import dotenv
from pytest_benchmark.plugin import benchmark

from pyc8y.client import CumulocityRestClient, BasicAuth


# @pytest.mark.asyncio(loop_scope='function')
def test(benchmark):
    dotenv.load_dotenv()

    async def run():
        async with CumulocityRestClient(
                base_url=os.environ['C8Y_BASEURL'],
                tenant_id=os.environ['C8Y_TENANT'],
                auth=BasicAuth(
                    os.environ['C8Y_USER'],
                    os.environ['C8Y_PASSWORD']),
        ) as c8y:
            await c8y.get("/inventory/managedObjects?pageSize=100")

    benchmark(lambda: asyncio.run(run()))
