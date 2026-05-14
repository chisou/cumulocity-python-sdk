# Copyright (c) 2026 Christoph Souris

import os

import pytest

from pyc8y.app import SimpleCumulocityApp, MultiTenantCumulocityApp
from pyc8y.auth import BearerAuth
from pyc8y.client import CumulocityClient
from pyc8y.model import ManagedObject
from pyc8y.rest import CumulocityRestClient

from tests.utils import build_auth_string, b64encode, sample_jwt


@pytest.fixture(name='token_app')
async def fix_token_app(test_environment):
    """Provide a token-based REST API instance."""
    # First, create an instance for basic auth
    c8y = SimpleCumulocityApp()
    # Obtain token via OAI Secure login
    auth, _ = await CumulocityRestClient.authenticate(
        base_url=c8y.base_url,
        tenant_id=c8y.tenant_id,
        username=os.environ['C8Y_USER'],
        password=os.environ['C8Y_PASSWORD'],
    )
    assert isinstance(auth, BearerAuth)
    await c8y.close()

    # Build token-based app
    token_c8y = CumulocityClient(
        base_url=c8y.base_url,
        tenant_id=c8y.tenant_id,
        auth=BearerAuth(auth.token),
    )
    yield token_c8y
    await token_c8y.close()


async def test_token_based_app_headers(token_app):
    """Verify that a token-based app only features a 'Bearer' auth header."""
    auth_header = token_app.auth.build_auth_header()
    assert auth_header.startswith('Bearer')


async def test_token_based_app(token_app):
    """Verify that a token-based app can be used for all kind of requests."""
    mo = await ManagedObject(token_app, name='test-object', type='test-object-type').create()
    mo['new_Fragment'] = {}
    await mo.update()
    await mo.delete()


async def test_oai_secure_login():
    """Verify that cookies from an OAI-Secure login are parsed correctly."""
    # First, create an instance for basic auth
    c8y = SimpleCumulocityApp()

    # (1) Submit auth request
    auth, xsrf_token = await CumulocityRestClient.authenticate(
        base_url=c8y.base_url,
        tenant_id=c8y.tenant_id,
        username=os.environ['C8Y_USER'],
        password=os.environ['C8Y_PASSWORD'],
    )
    # -> should yield both tokens
    assert isinstance(auth, BearerAuth)
    assert xsrf_token

    # (2) Build an OAI-based request
    # Cumulocity forwards the cookies as well as the XSRF token _and_
    # a phony Basic Auth header which contains tenant ID and username
    # with a fake password to ensure backwards compatibility.
    headers={
        'Accept': 'application/json',
        'Authorization': build_auth_string(b64encode(f'{c8y.tenant_id}/{os.environ["C8Y_USER"]}:<fake password>')),
        'X-Xsrf-Token': xsrf_token,
    }
    cookies = {'authorization': auth.token}

    # -> user scope instance can be obtained
    c8y_user = await c8y.get_user_instance(headers, cookies)
    assert isinstance(c8y_user.auth, BearerAuth)
    assert c8y_user.auth.token == auth.token

    await c8y.close()


async def test_get_user_instance_aiohttp_types(test_environment):
    """Verify that get_user_instance handles aiohttp-style CIMultiDict headers and cookies."""
    from multidict import CIMultiDict

    c8y = SimpleCumulocityApp()
    token = sample_jwt()

    # Bearer token in Authorization header
    c8y_user = await c8y.get_user_instance(headers=CIMultiDict({'Authorization': f'Bearer {token}'}))
    assert isinstance(c8y_user.auth, BearerAuth)
    assert c8y_user.auth.token == token

    # JWT in authorization cookie (aiohttp web.Request.cookies is a plain Mapping[str, str])
    c8y_user = await c8y.get_user_instance(cookies={'authorization': token})
    assert isinstance(c8y_user.auth, BearerAuth)
    assert c8y_user.auth.token == token

    # OAI Secure pattern: fake Basic in header + JWT in cookie -> cookie wins
    fake_basic = build_auth_string(b64encode(f't12345/user:<fake>'))
    c8y_user = await c8y.get_user_instance(
        headers=CIMultiDict({'Authorization': fake_basic}),
        cookies={'authorization': token},
    )
    assert isinstance(c8y_user.auth, BearerAuth)
    assert c8y_user.auth.token == token

    await c8y.close()


async def test_get_user_instance_fastapi_types(test_environment):
    """Verify that get_user_instance handles FastAPI (Starlette) headers and cookies."""
    pytest.importorskip('starlette')
    from starlette.datastructures import Headers as StarletteHeaders

    c8y = SimpleCumulocityApp()
    token = sample_jwt()

    # Bearer token in Authorization header (Starlette normalises header names to lowercase)
    c8y_user = await c8y.get_user_instance(headers=StarletteHeaders(headers={'authorization': f'Bearer {token}'}))
    assert isinstance(c8y_user.auth, BearerAuth)
    assert c8y_user.auth.token == token

    # JWT in authorization cookie (FastAPI exposes cookies as plain dict[str, str])
    c8y_user = await c8y.get_user_instance(cookies={'authorization': token})
    assert isinstance(c8y_user.auth, BearerAuth)
    assert c8y_user.auth.token == token

    # OAI Secure pattern: fake Basic in header + JWT in cookie -> cookie wins
    fake_basic = build_auth_string(b64encode(f't12345/user:<fake>'))
    c8y_user = await c8y.get_user_instance(
        headers=StarletteHeaders(headers={'authorization': fake_basic}),
        cookies={'authorization': token},
    )
    assert isinstance(c8y_user.auth, BearerAuth)
    assert c8y_user.auth.token == token

    await c8y.close()


async def test_get_user_instance_quart_types(test_environment):
    """Verify that get_user_instance handles Quart (Werkzeug) headers and cookies."""
    pytest.importorskip('werkzeug')
    from werkzeug.datastructures import Headers as WerkzeugHeaders

    c8y = SimpleCumulocityApp()
    token = sample_jwt()

    # Bearer token in Authorization header
    c8y_user = await c8y.get_user_instance(headers=WerkzeugHeaders([('Authorization', f'Bearer {token}')]))
    assert isinstance(c8y_user.auth, BearerAuth)
    assert c8y_user.auth.token == token

    # JWT in authorization cookie (Quart exposes cookies as ImmutableMultiDict[str, str])
    c8y_user = await c8y.get_user_instance(cookies={'authorization': token})
    assert isinstance(c8y_user.auth, BearerAuth)
    assert c8y_user.auth.token == token

    # OAI Secure pattern: fake Basic in header + JWT in cookie -> cookie wins
    fake_basic = build_auth_string(b64encode(f't12345/user:<fake>'))
    c8y_user = await c8y.get_user_instance(
        headers=WerkzeugHeaders([('Authorization', fake_basic)]),
        cookies={'authorization': token},
    )
    assert isinstance(c8y_user.auth, BearerAuth)
    assert c8y_user.auth.token == token

    await c8y.close()


async def test_context_manager(test_environment):
    """Verify that the Apps can be used as context managers."""

    async with SimpleCumulocityApp() as c8y:
        assert c8y.username

    async with MultiTenantCumulocityApp() as c8y:
        assert c8y.bootstrap_instance.username
