# Copyright (c) 2025 Cumulocity GmbH

from contextlib import suppress
from unittest.mock import AsyncMock
from urllib.parse import unquote_plus, urlencode

import pytest

from pyc8y.auth import BasicAuth
from pyc8y.client import CumulocityClient
from pyc8y.model.application import Application, ApplicationSetting, ApplicationSubscription, Applications

from tests.utils import isolate_last_call_arg


async def isolate_call_url(fun, **kwargs):
    """Call an Applications API function and isolate the request URL for further assertions."""
    c8y = CumulocityClient(base_url='some.host.com', tenant_id='t123', auth=BasicAuth('user', 'pass'))
    c8y.get = AsyncMock(return_value={'applications': []})
    await fun(c8y.applications, **kwargs)
    resource = isolate_last_call_arg(c8y.get, 'resource', 0)
    params = None
    with suppress(KeyError):
        params = isolate_last_call_arg(c8y.get, 'params', 1)
    return unquote_plus(resource) if not params else f"{resource}?{urlencode(params)}"


@pytest.mark.parametrize('fun', [
    Applications.get_all,
])
@pytest.mark.parametrize('params, expected, not_expected', [
    ({'expression': 'EX', 'type': 'T'}, ['?EX'], ['type']),
    ({'type': 'T', 'name': 'myname', 'owner': 'O', 'user': 'U'},
     ['type=T', 'name=myname', 'owner=O', 'user=U'],
     []),
    ({'tenant': 'T', 'subscriber': 'S', 'provided_for': 'P'},
     ['tenant=T', 'subscriber=S', 'providedFor=P'],
     ['_']),
    ({'has_versions': False}, ['hasVersions=false'], ['_']),
    ({'snake_case': 'SC', 'pascalCase': 'PC'},
     ['snakeCase=SC', 'pascalCase=PC'],
     ['_']),
], ids=[
    'expression',
    'type+name+owner+user',
    'tenant+subscriber+provided_for',
    'has_versions',
    'kwargs',
])
async def test_select(fun, params, expected, not_expected):
    """Verify that the select function's parameters are processed as expected."""
    resource = await isolate_call_url(fun, **params)
    for e in expected:
        assert e in resource
    for ne in not_expected:
        assert ne not in resource


async def test_select_as_values():
    """Verify that select as_values works as expected."""
    application_jsons = [
        {'id': '1', 'type': 'HOSTED', 'name': 'app1', 'key': 'app1-key',
         'owner': {'tenant': {'id': 'management'}}},
        {'id': '2', 'type': 'MICROSERVICE', 'name': 'app2', 'key': 'app2-key',
         'owner': {'tenant': {'id': 'management'}}},
    ]
    c8y = CumulocityClient(base_url='some.host.com', tenant_id='t123', auth=BasicAuth('user', 'pass'))
    c8y.get = AsyncMock(side_effect=[
        {'applications': application_jsons},
        {'applications': []},
    ])
    result = await c8y.applications.get_all(as_values=['id', 'type', 'name'])
    assert result == [
        ('1', 'HOSTED', 'app1'),
        ('2', 'MICROSERVICE', 'app2'),
    ]


def test_application_setting_parsing():
    """Verify that parsing an ApplicationSetting from JSON works."""
    setting_json = {
        'key': 'my.setting',
        'defaultValue': 'default',
        'valueSchema': {'type': 'STRING'},
        'editable': True,
        'inheritFromOwner': False,
    }
    setting = ApplicationSetting.from_json(setting_json)

    assert setting.key == setting_json['key']
    assert setting.default_value == setting_json['defaultValue']
    assert setting.value_schema.type == setting_json['valueSchema']['type']
    assert setting.editable is True
    assert setting.inherited is False


def test_application_subscription_parsing():
    """Verify that parsing an ApplicationSubscription from JSON works."""
    subscription_json = {
        'tenant': 't12345',
        'name': 'bootstrap',
        'password': 'secret',
    }
    subscription = ApplicationSubscription.from_json(subscription_json)

    assert subscription.tenant_id == subscription_json['tenant']
    assert subscription.username == subscription_json['name']
    assert subscription.password == subscription_json['password']
