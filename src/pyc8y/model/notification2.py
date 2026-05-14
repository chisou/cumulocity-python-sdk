# Copyright (c) 2026 Christoph Souris


import json as js
import uuid
from typing import AsyncIterator, Self
import urllib.parse

from pyc8y.rest import CumulocityRestClient
from pyc8y.model.model_base import (
    CumulocityObject,
    CumulocityResource,
    json_property,
    map_params,
    resolve_page_size,
)
from pyc8y.types import SubscriptionMeta


class Subscription(CumulocityObject):
    """Represents a Notification 2.0 subscription within the database.

    Instances of this class are returned by functions of the corresponding
    Subscriptions API. Use this class to create new subscriptions.

    See also: https://cumulocity.com/api/core/#tag/Subscriptions
    """

    _meta = SubscriptionMeta

    class Context:
        """Notification context types."""

        MANAGED_OBJECT = "mo"
        TENANT = "tenant"

    class ApiFilter:
        """Notification API filter types."""

        ANY = "*"
        ALARMS = "alarms"
        ALARMS_WITH_CHILDREN = "alarmsWithChildren"
        EVENTS = "events"
        EVENTS_WITH_CHILDREN = "eventsWithChildren"
        MANAGED_OBJECTS = "managedobjects"
        MEASUREMENTS = "measurements"
        OPERATIONS = "operations"

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        *,
        name: str | None = None,
        context: str | None = None,
        source_id: str | None = None,
        api_filter: list[str] | None = None,
        type_filter: str | None = None,
        fragments: list[str] | None = None,
        non_persistent: bool | None = None,
    ):
        super().__init__(c8y)
        self.name = name
        self.context = context
        self.source_id = source_id
        self.non_persistent = non_persistent
        self.api_filter = api_filter
        self.type_filter = type_filter
        self.fragments = fragments

    name = json_property("subscription")
    context = json_property("context")
    non_persistent = json_property("nonPersistent")
    fragments = json_property("fragmentsToCopy")

    @property
    def source_id(self) -> str | None:
        """Managed object ID the subscription is for."""
        raw = self._json.get("source")
        return raw["id"] if raw else None

    @source_id.setter
    def source_id(self, value: str | None):
        if value is not None:
            self._staged_json["source"] = {"id": value}

    @property
    def api_filter(self) -> list[str] | None:
        """List of APIs/resources this subscription covers."""
        sf = self._json.get("subscriptionFilter")
        return sf.get("apis") if sf else None

    @api_filter.setter
    def api_filter(self, value: list[str] | None):
        if value is not None:
            sf = self._staged_json.get("subscriptionFilter", {})
            sf["apis"] = value
            self._staged_json["subscriptionFilter"] = sf

    @property
    def type_filter(self) -> str | None:
        """Object type the subscription is for."""
        sf = self._json.get("subscriptionFilter")
        return sf.get("typeFilter") if sf else None

    @type_filter.setter
    def type_filter(self, value: str | None):
        if value is not None:
            sf = self._staged_json.get("subscriptionFilter", {})
            sf["typeFilter"] = value
            self._staged_json["subscriptionFilter"] = sf

    @classmethod
    def from_json(cls, json: dict, c8y: CumulocityRestClient | None = None) -> Self:
        return cls._build(json, c8y=c8y)

    async def create(self) -> Self:
        """Create a new subscription within the database.

        Returns:
            A fresh Subscription instance representing the created subscription.
        """
        return await self._create()


class Subscriptions(CumulocityResource[Subscription]):
    """Provides access to the Notification 2.0 Subscriptions API.

    This class can be used for get, search for, create, and
    delete Notification2 subscriptions within the Cumulocity database.

    See also: https://cumulocity.com/api/core/#tag/Subscriptions
              https://cumulocity.com/guides/reference/notifications/
    """

    _meta = SubscriptionMeta
    _object_type = Subscription

    async def get(self, subscription_id: str) -> Subscription:
        """Retrieve a specific subscription from the database.

        Args:
            subscription_id (str):  Subscription ID

        Returns:
            A Subscription instance
        """
        return await self._get(subscription_id)

    async def get_count(
        self,
        expression: str | None = None,
        *,
        context: str | None = None,
        source: str | None = None,
        subscription: str | None = None,
        type_filter: str | None = None,
        **kwargs,
    ) -> int:
        """Calculate the number of potential results of a database query.

        Returns:
            Number of potential results
        """
        params = (
            map_params(
                page_size=1,
                context=context,
                source=source,
                subscription=subscription,
                typeFilter=type_filter,
                **kwargs,
            )
            if not expression
            else ()
        )
        return await self._get_count(expression=expression, params=params)

    def select(
        self,
        expression: str | None = None,
        *,
        context: str | None = None,
        source: str | None = None,
        subscription: str | None = None,
        type_filter: str | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[Subscription]:
        """Query the database for subscriptions and iterate over the results.

        Args:
            expression (str):  Arbitrary filter expression; all other filters
                are ignored if this is provided
            context (str):  Subscription context
            source (str):  Managed object ID the subscription is for
            subscription (str):  The subscription name
            type_filter (str):  Object type filter
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int):  Pull a specific page only
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of Subscription instances
        """
        page_size = resolve_page_size(page_size, limit)
        params = (
            map_params(
                context=context,
                source=source,
                subscription=subscription,
                typeFilter=type_filter,
                page_size=page_size,
                **kwargs,
            )
            if not expression
            else ()
        )
        return self._iterate(
            expression=expression,
            params=params,
            page_number=page_number,
            limit=limit,
            workers=workers,
        )

    async def get_all(
        self,
        expression: str | None = None,
        *,
        context: str | None = None,
        source: str | None = None,
        subscription: str | None = None,
        type_filter: str | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[Subscription]:
        """Query the database for subscriptions and return the results as list.

        See `select` for a documentation of arguments.

        Returns:
            List of Subscription instances
        """
        return [
            x
            async for x in self.select(
                expression=expression,
                context=context,
                source=source,
                subscription=subscription,
                type_filter=type_filter,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                workers=workers,
                **kwargs,
            )
        ]

    async def create(self, *subscriptions: Subscription, workers: int | None = None) -> None:
        """Create subscriptions within the database.

        Args:
            *subscriptions (Subscription):  Collection of Subscription instances
            workers (int):  Number of parallel workers
        """
        await self._create(*subscriptions, workers=workers)

    async def delete_by(
        self,
        expression: str | None = None,
        *,
        context: str | None = None,
        source: str | None = None,
    ) -> None:
        """Delete subscriptions within the database.

        Args:
            expression (str):  Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided
            context (str):  Subscription context
            source (str):  Managed object ID the subscription is for
        """
        if expression:
            await self.c8y.delete(f"{self.resource_path}?{expression}")
            return
        params = map_params(context=context, source=source)
        await self.c8y.delete(self.resource_path, params=params)


class Tokens:
    """Provides access to the Notification 2.0 token generation API.

    See also: https://cumulocity.com/api/core/#tag/Tokens
              https://cumulocity.com/guides/reference/notifications/
    """

    _subscriber_uuid = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/Cumulocity-IoT/cumulocity-python-api")
    _default_subscriber = "c8yapi" + str(_subscriber_uuid).replace("-", "")

    def __init__(self, c8y: CumulocityRestClient):
        self.c8y = c8y
        self.host = urllib.parse.urlparse(c8y.base_url).netloc

    async def generate(
        self,
        subscription: str,
        expires: int = 1440,
        subscriber: str | None = None,
        signed: bool | None = None,
        shared: bool | None = None,
        non_persistent: bool | None = None,
    ) -> str:
        """Generate a new access token.

        Args:
            subscription (str):  Subscription name
            expires (int):  Expiration time in minutes
            subscriber (str):  Subscriber ID; a UUID-based default is used if None
            signed (bool):  Whether the token should be signed
            shared (bool):  Whether the token is used to create a shared consumer
            non_persistent (bool):  Whether the token refers to the non-persistent subscription

        Returns:
            JWT access token as string
        """
        td_json = self._build_token_definition(subscription, expires, subscriber, signed, shared, non_persistent)
        token_json = await self.c8y.post("notification2/token", json=td_json)
        return token_json["token"]

    async def unsubscribe(self, token: str) -> None:
        """Invalidate a token and unsubscribe a subscriber.

        Args:
            token (str):  Subscribed token
        """
        result_json = await self.c8y.post(f"notification2/unsubscribe?token={token}", json={})
        if result_json.get("result") != "DONE":
            raise RuntimeError(f"Unexpected response: {js.dumps(result_json)}")

    def build_websocket_uri(self, token: str, consumer: str | None = None) -> str:
        """Build websocket access URL.

        Args:
            token (str):  Subscriber access token
            consumer (str):  Optional consumer ID for sticky connections

        Returns:
            A websocket (ws(s)://) URL to access the subscriber channel
        """
        protocol = "wss" if self.c8y.base_url.startswith("https") else "ws"
        consumer_param = f"&consumer={consumer}" if consumer else ""
        return f"{protocol}://{self.host}/notification2/consumer/?token={token}{consumer_param}"

    def _build_token_definition(
        self,
        subscription: str,
        expires: int,
        subscriber: str | None = None,
        signed: bool | None = None,
        shared: bool | None = None,
        non_persistent: bool | None = None,
    ) -> dict:
        body = {
            "subscriber": subscriber or self._default_subscriber,
            "subscription": subscription,
            "expiresInMinutes": expires,
        }
        if signed is not None:
            body["signed"] = signed
        if shared is not None:
            body["shared"] = shared
        if non_persistent is not None:
            body["nonPersistent"] = non_persistent
        return body
