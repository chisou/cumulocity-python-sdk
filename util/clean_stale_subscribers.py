"""Tool to remove stale subscribers from failed Notification 2.0 tests."""

import asyncio
import re

from pyc8y import get_client

async def main():
    c8y = await get_client(log_level="DEBUG")
    tenant_id = c8y.tenant_id
    topics_json = await c8y.get(
        f"/service/messaging-management/tenants/{tenant_id}"
        "/namespaces/relnotif/topics?pageSize=1000"
    )

    async def check_topic(topic_name):
        if not re.match(r"[a-z]+Subscription", topic_name):
            print(f"Skipping (name mismatch): {topic_name}")
            return
        # read subscribers
        subscribers_json = await c8y.get(
            f"/service/messaging-management/tenants/{tenant_id}"
            f"/namespaces/relnotif/topics/{topic_name}/types/persistent/subscribers"
        )
        subscribers = [x["name"] for x in subscribers_json["subscribers"]]
        if not subscribers:
            print(f"Skipping (no subscribers): {topic_name}")
            return
        if subscribers[0] != topic_name and subscribers[0][:-1] != topic_name:
            print(f"Skipping (not identical): {topic_name}, {subscribers[0]}")
            return
        # remove subscribers
        await asyncio.gather(*[
            c8y.delete(
                f"/service/messaging-management/tenants/{tenant_id}"
                f"/namespaces/relnotif/topics/{topic_name}/types/persistent/subscribers/{subscriber}"
            )
            for subscriber in subscribers])

    await asyncio.gather(*[check_topic(topic["name"]) for topic in topics_json["topics"]])


asyncio.run(main())