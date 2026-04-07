# Copyright (c) 2025 Cumulocity GmbH
from contextlib import suppress

import pytest

from pyc8y.auth import BasicAuth
from pyc8y.client import CumulocityClient
from pyc8y.model import TenantOptions, TenantOption


async def test_select_name(live_c8y: CumulocityClient):
    """Verify that select by name works."""
    apps = await live_c8y.applications.get_all(name='devicemanagement')
    assert apps
    app = apps[0]
    assert app.name == 'devicemanagement'
    assert app.owner == 'management'
    assert app.type == 'HOSTED'
    assert app.availability == 'MARKET'


async def test_select_owner(live_c8y: CumulocityClient):
    """Verify that select by owner works."""
    # this test assumes, that the live tenant owns at least one application
    apps = await live_c8y.applications.get_all(owner=live_c8y.tenant_id)
    assert apps


@pytest.mark.parametrize('param, param_func', [
    ('type', lambda x: 'HOSTED'),
    ('user', lambda x: 'service_sms-gateway'),
    ('tenant', lambda x: x.tenant_id),
    ('subscriber', lambda x: x.tenant_id),
    ('provided_for', lambda x: x.tenant_id),
])
async def test_selects(live_c8y: CumulocityClient, param, param_func):
    """Verify that select/get_all works with all available filters."""
    kwargs = {param: param_func(live_c8y)}
    apps = await live_c8y.applications.get_all(**kwargs)
    assert apps


@pytest.fixture(name='bootstrap_api', scope='module')
async def fix_bootstrap_api(app_factory):
    """Provide a CumulocityClient instance with bootstrap permissions."""
    app_name = 'inttest-application'
    required_roles = ['ROLE_OPTION_MANAGEMENT_READ', 'ROLE_OPTION_MANAGEMENT_ADMIN']
    instance = await app_factory(app_name, required_roles)
    yield instance
    await instance.close()


async def test_get_current(bootstrap_api: CumulocityClient):
    """Verify that the current application can be read using a bootstrap instance."""
    app = await bootstrap_api.applications.get_current()
    # the format of the username is "bootstrapuser_<appname>"
    bootstrap_app_name = bootstrap_api.username.split('_', 1)[1]
    assert app.name == bootstrap_app_name


async def test_tenant_options(live_c8y: CumulocityClient, bootstrap_api: CumulocityClient):
    """Verify that the current application's tenant options can be read using
    a subscribed instance."""

    app_category = (await bootstrap_api.applications.get_current()).resolve_tenant_option_category()

    try:
        # (1) create options as admin user
        await live_c8y.tenant_options.create(
            TenantOption(category=app_category, key="admin_key", value="some admin value"),
            TenantOption(category=app_category, key="admin_secret", value="admins secret value", encrypted=True),
            # workers=5
        )

        # (2) create options as service user
        subscriber = (await bootstrap_api.applications.get_current_subscriptions())[0]
        client: CumulocityClient = CumulocityClient(
            base_url=live_c8y.base_url,
            tenant_id=subscriber.tenant_id,
            auth=BasicAuth(subscriber.username, subscriber.password),
        )
        await client.tenant_options.create(
            TenantOption(category=app_category, key="app_secret", value="secret app value", encrypted=True),
            TenantOption(category=app_category, key="app_key", value="some app value"),
            # workers=5
        )

        # (3) retrieve all options as bootstrap user
        all_options1 = await client.applications.get_current_settings()
        assert set(all_options1.keys()) == {'credentials.app_secret', 'app_key', 'credentials.admin_secret', 'admin_key'}

        # (4) retrieve all options as service user
        all_options2 = await client.tenant_options.get_values(app_category)
        assert set(all_options2.keys()) == {'app_secret', 'app_key', 'admin_secret', 'admin_key'}

    finally:
        # (5) cleanup
        for key in (await live_c8y.tenant_options.get_values(app_category)).keys():
            with suppress(KeyError):
                await live_c8y.tenant_options.delete(category=app_category, key=key)


async def test_get_current_settings(bootstrap_api: CumulocityClient):
    """Verify that the current application's settings can be read using
    a bootstrap instance."""
    assert await bootstrap_api.applications.get_current_settings() is not None


async def test_get_current_subscriptions(live_c8y: CumulocityClient, bootstrap_api: CumulocityClient):
    """Verify that the current application's subscriptions can be read using
    a bootstrap instance."""
    subscriptions = await bootstrap_api.applications.get_current_subscriptions()
    assert len(subscriptions) == 1
    assert subscriptions[0].tenant_id == live_c8y.tenant_id
