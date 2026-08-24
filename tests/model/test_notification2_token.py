# Copyright (c) 2026 Christoph Souris

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyc8y.model.notification2 import Tokens


@pytest.mark.parametrize("tls, consumer, expected", [
    (False, False, "ws://c8y.com/notification2/consumer/?token={}"),
    (True,  False, "wss://c8y.com/notification2/consumer/?token={}"),
    (False, True,  "ws://c8y.com/notification2/consumer/?token={}&consumer={}"),
    (True,  True,  "wss://c8y.com/notification2/consumer/?token={}&consumer={}"),
])
def test_uri_generator(tls, consumer, expected):
    """Verify that building the websocket URI works as expected."""
    token = str(uuid.uuid4())
    consumer_id = str(uuid.uuid4()) if consumer else None

    protocol = "https" if tls else "http"
    c8y = MagicMock()
    c8y.base_url = f"{protocol}://c8y.com"

    uri = Tokens(c8y).build_websocket_uri(token, consumer_id)

    assert uri == expected.format(token, consumer_id)


@pytest.mark.parametrize("subscription, expiry, subscriber, shared, signed, non_persistent", [
    ("sub", 123, "id123", None, None, None),
    ("sub", 0,   None,    True, False, True),
    ("sub", 123, "id123", False, True, False),
])
async def test_generate(subscription, expiry, subscriber, shared, signed, non_persistent):
    """Verify that token generation works as expected."""
    c8y = MagicMock()
    c8y.base_url = "https://c8y.com"
    c8y.post = AsyncMock(return_value={"token": "TOKEN"})

    await Tokens(c8y).generate(
        subscription=subscription,
        expires=expiry,
        subscriber=subscriber,
        shared=shared,
        signed=signed,
        non_persistent=non_persistent,
    )

    td_json = c8y.post.call_args[1]["json"]

    assert td_json["subscription"] == subscription
    assert td_json["expiresInMinutes"] == expiry

    if subscriber:
        assert td_json["subscriber"] == subscriber
    else:
        assert "c8yapi" in td_json["subscriber"]

    if shared is not None:
        assert td_json["shared"] == shared
    if signed is not None:
        assert td_json["signed"] == signed
    if non_persistent is not None:
        assert td_json["nonPersistent"] == non_persistent
