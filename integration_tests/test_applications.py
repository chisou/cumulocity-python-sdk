# Copyright (c) 2025 Cumulocity GmbH

import pytest

from pyc8y.client import CumulocityClient


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
