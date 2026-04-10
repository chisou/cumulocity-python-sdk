# Copyright (c) 2026 Christoph Souris

import os
import time
from unittest.mock import AsyncMock, patch

import pytest

import pyc8y.app as app_module
from pyc8y.app import get_client
from pyc8y.auth import BearerAuth
from pyc8y.client import CumulocityClient
from pyc8y.rest import HttpError, MissingTfaError

from tests.utils import sample_jwt


def valid_token(**kwargs) -> str:
    """JWT token that will not be considered expired."""
    return sample_jwt(
        aud='https://test.cumulocity.com',
        ten='t12345',
        sub="user",
        exp=int(time.time()) + 7 * 24 * 3600,
        **kwargs,
    )


def expired_token(**kwargs) -> str:
    """JWT token that will be considered expired (within 1-hour grace period)."""
    return sample_jwt(
        aud='https://test.cumulocity.com',
        ten='t12345',
        sub="user",
        exp=int(time.time()) - 3600,
        **kwargs,
    )


@pytest.fixture(autouse=True)
def clear_client_cache():
    """Ensure the module-level client cache is empty for every test."""
    app_module._clients.clear()
    yield
    app_module._clients.clear()


async def test_valid_token_in_env():
    """Verifies that a proper token is used directly."""
    token = valid_token()
    with patch.dict(os.environ, {'C8Y_TOKEN': token}, clear=True):
        with patch('pyc8y.rest.CumulocityRestClient.authenticate', new_callable=AsyncMock) as mock_auth:
            c8y = await get_client()

    mock_auth.assert_not_called()
    assert isinstance(c8y, CumulocityClient)
    assert isinstance(c8y.auth, BearerAuth)
    assert c8y.auth.token == token
    assert c8y.tenant_id == 't12345'


async def test_expired_token_falls_through(capsys):
    """Verifies that an expired token is tossed."""
    env = {
        'C8Y_TOKEN': expired_token(),
        'C8Y_BASEURL': 'https://test.cumulocity.com',
        'C8Y_TENANT': 't12345',
        'C8Y_USER': "user",
        'C8Y_PASSWORD': "pass",
    }
    auth = BearerAuth("token")
    with patch.dict(os.environ, env, clear=True):
        with patch('pyc8y.rest.CumulocityRestClient.authenticate', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = (auth, None)
            c8y = await get_client()

    assert 'invalidated' in capsys.readouterr().out
    mock_auth.assert_called_once()
    assert c8y.auth is auth


async def test_credentials_from_env():
    """Verifies that a proper environment does not require prompts."""
    env = {
        'C8Y_BASEURL': 'https://test.cumulocity.com',
        'C8Y_TENANT': 't12345',
        'C8Y_USER': "user",
        'C8Y_PASSWORD': "pass",
    }
    auth = BearerAuth("token")
    with patch.dict(os.environ, env, clear=True):
        with patch('pyc8y.rest.CumulocityRestClient.authenticate', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = (auth, None)
            with patch('builtins.input') as mock_input:
                c8y = await get_client()

    mock_input.assert_not_called()
    mock_auth.assert_called_once_with(
        base_url='https://test.cumulocity.com',
        tenant_id='t12345',
        username="user",
        password="pass",
        tfa_token=None,
    )
    assert isinstance(c8y, CumulocityClient)
    assert c8y.auth is auth

async def test_explicit_args_override_env():
    """Verify that explicit args override environment variables."""
    env = {
        'C8Y_BASEURL': 'https://from.env.com',
        'C8Y_TENANT': 'env_tenant',
        'C8Y_USER': 'env_user',
        'C8Y_PASSWORD': 'env_pass',
    }

    with patch.dict(os.environ, env, clear=True):
        with patch('pyc8y.rest.CumulocityRestClient.authenticate', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = (BearerAuth("token"), None)
            await get_client(
                base_url='https://test.cumulocity.com',
                tenant_id='t12345',
                username="user",
                password="pass",
            )

    _, kwargs = mock_auth.call_args
    assert kwargs['base_url'] == 'https://test.cumulocity.com'
    assert kwargs['tenant_id'] == 't12345'
    assert kwargs['username'] == "user"
    assert kwargs['password'] == "pass"


async def test_same_client_returned_on_repeated_calls():
    """Repeated calls with identical parameters return the same client."""
    env = {
        'C8Y_BASEURL': 'https://test.cumulocity.com',
        'C8Y_TENANT': 't12345',
        'C8Y_USER': "user",
        'C8Y_PASSWORD': "pass",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch('pyc8y.rest.CumulocityRestClient.authenticate', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = (BearerAuth("token"), None)
            c8y1 = await get_client()
            c8y2 = await get_client()

    assert c8y1 is c8y2
    mock_auth.assert_called_once()


async def test_different_users_get_different_clients():
    """Different usernames produce separate cached clients."""
    with patch('pyc8y.rest.CumulocityRestClient.authenticate', new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = (BearerAuth("token"), None)
        c8y1 = await get_client(base_url='https://test.cumulocity.com', tenant_id='t12345',
                                username='user_a', password="pass")
        c8y2 = await get_client(base_url='https://test.cumulocity.com', tenant_id='t12345',
                                username='user_b', password="pass")

    assert c8y1 is not c8y2
    assert mock_auth.call_count == 2


async def test_interactive_prompts_for_missing_values():
    """Missing environment variables are read from user."""
    with patch.dict(os.environ, {}, clear=True):
        with patch('pyc8y.rest.CumulocityRestClient.authenticate', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = (BearerAuth("token"), None)
            with patch('builtins.input', side_effect=['https://test.cumulocity.com', 't12345', "user"]) as mock_input:
                with patch('getpass.getpass', return_value="pass") as mock_getpass:
                    c8y = await get_client()

    assert mock_input.call_count == 3   # 'https://test.cumulocity.com', tenant_id, username
    mock_getpass.assert_called_once()   # password
    assert isinstance(c8y, CumulocityClient)


async def test_wrong_password_reprompts():
    """Invalid username or password (HttpError) re-prompts."""
    env = {'C8Y_BASEURL': 'https://test.cumulocity.com', 'C8Y_TENANT': 't12345', 'C8Y_USER': "user"}
    with patch.dict(os.environ, env, clear=True):
        with patch('pyc8y.rest.CumulocityRestClient.authenticate', new_callable=AsyncMock) as mock_auth:
            mock_auth.side_effect = [
                HttpError('POST', 'https://test.cumulocity.com', 401, 'Unauthorized'),
                (BearerAuth("token"), None),
            ]
            with patch('getpass.getpass', side_effect=['wrong_password', "pass"]):
                c8y = await get_client()

    assert mock_auth.call_count == 2
    assert isinstance(c8y, CumulocityClient)


async def test_tfa_required_prompts_for_code():
    """A missing 2nd factor results in read from user and 2nd attempt."""
    env = {
        'C8Y_BASEURL': 'https://test.cumulocity.com',
        'C8Y_TENANT': 't12345',
        'C8Y_USER': "user",
        'C8Y_PASSWORD': "pass",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch('pyc8y.rest.CumulocityRestClient.authenticate', new_callable=AsyncMock) as mock_auth:
            mock_auth.side_effect = [
                MissingTfaError('POST', 'https://test.cumulocity.com', 'TFA required'),
                (BearerAuth("token"), None),
            ]
            with patch('builtins.input', return_value='123456') as mock_input:
                c8y = await get_client()

    mock_input.assert_called_once()
    assert mock_auth.call_count == 2

    # second call includes the TFA code
    _, kwargs = mock_auth.call_args
    assert kwargs['tfa_token'] == '123456'
    assert isinstance(c8y, CumulocityClient)
