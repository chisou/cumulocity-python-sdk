# Copyright (c) 2026 Christoph Souris

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from pyc8y.auth import BasicAuth
from pyc8y.registry import Credentials, DeviceRegistryClient


def test_auth():
    """Verify that the basic auth information is piped through correctly."""
    base_url = "https://baseurl.com:8989"
    tenant_id = "t12345"
    username = "someuser"
    password = "somepass"

    auth = BasicAuth(username=f"{tenant_id}/{username}", password=password)
    client = DeviceRegistryClient(base_url=base_url, tenant_id=tenant_id, auth=auth)

    assert client.username == username
    assert client.tenant_id == tenant_id
    assert isinstance(client.auth, BasicAuth)
    assert client.auth.username == f"{tenant_id}/{username}"
    assert client.auth.password == password


async def test_await_credentials():
    """Verify that await_credentials polls until credentials are available."""
    tenant_id = "t12345"
    device_serial = str(uuid.uuid1())

    auth = BasicAuth(username=f"{tenant_id}/someuser", password="somepass")
    client = DeviceRegistryClient(
        base_url="https://baseurl.com:8989",
        tenant_id=tenant_id,
        auth=auth,
    )

    response_404 = MagicMock()
    response_404.status = 404

    response_201 = MagicMock()
    response_201.status = 201
    response_201.json = AsyncMock(
        return_value={
            "tenantId": tenant_id,
            "username": "device_" + device_serial,
            "password": "password12345",
        }
    )

    mock_session = MagicMock()
    mock_session.post = AsyncMock(side_effect=[response_404, response_201])
    client._session = mock_session

    with patch("time.sleep"):
        credentials = await client.await_credentials(device_serial)

    assert isinstance(credentials, Credentials)
    assert credentials.tenant_id == tenant_id
    assert credentials.username == "device_" + device_serial
    assert credentials.password == "password12345"

    mock_session.post.assert_called_with(
        "/devicecontrol/deviceCredentials",
        json={"id": device_serial},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )