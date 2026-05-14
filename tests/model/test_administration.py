# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris

from unittest.mock import AsyncMock, MagicMock
from urllib.parse import unquote_plus

import pytest

from pyc8y.model.user import Users


async def _isolate_call_url(**kwargs):
    """Call Users.get_all and return the URL/query string."""
    c8y = MagicMock()
    c8y.tenant_id = 't123'
    c8y.get = AsyncMock(return_value={'users': [], 'statistics': {'totalPages': 1}})
    users = Users(c8y=c8y)
    await users.get_all(**kwargs)
    assert c8y.get.called
    call_args, call_kwargs = c8y.get.call_args
    # resource is positional 1st arg, params is positional 2nd arg (per Users.select fetch_page)
    resource = call_args[0]
    params = call_args[1] if len(call_args) > 1 else call_kwargs.get('params') or ()
    if params:
        query_string = '&'.join(f'{k}={v}' for k, v in params)
        resource = f'{resource}?{query_string}'
    return unquote_plus(resource)


@pytest.mark.parametrize('params, expected, not_expected', [
    ({'username': 'U', 'owner': 'O'},
     ['username=U', 'owner=O'],
     []),
    ({'only_devices': False, 'with_subusers_count': True},
     ['onlyDevices=false', 'withSubusersCount=true'],
     ['_']),
], ids=[
    'username+owner',
    'only_devices+with_subusers_count',
])
async def test_select_users(params, expected, not_expected):
    """Verify that user selection parameters are processed as expected."""
    resource = await _isolate_call_url(**params)

    for e in expected:
        assert e in resource, f"Expected '{e}' in URL: {resource}"
    for ne in not_expected:
        assert ne not in resource, f"Did not expect '{ne}' in URL: {resource}"


async def test_select_as_values():
    """Verify that select as values works as expected."""
    jsons = [
        {'userName': 'user1',
         'enabled': True,
         'applications': [],
         'customProperties': {'p1': 'v1', 'p2': 'v2'}},
        {'userName': 'user2',
         'enabled': False,
         'applications': [{'a': 1}, {'b': 2}],
         'customProperties': {'p1': 'v2'},
         'phone': '+123'},
    ]

    c8y = MagicMock()
    c8y.tenant_id = 't123'
    c8y.get = AsyncMock(side_effect=[{'users': jsons}, {'users': []}])
    api = Users(c8y)

    result = await api.get_all(as_values=[
        'user_name', 'enabled', 'applications', 'customProperties.p1', 'customProperties.p2', 'phone'])
    assert result == [
        ('user1', True, [], 'v1', 'v2', None),
        ('user2', False, [{'a': 1}, {'b': 2}], 'v2', None, '+123'),
    ]

    c8y.get = AsyncMock(side_effect=[{'users': jsons}, {'users': []}])
    result = await api.get_all(as_values=[
        'userName', 'enabled', 'applications', 'custom_properties.p1', ('customProperties.p2', 'v3'), ('phone', '')])
    assert result == [
        ('user1', True, [], 'v1', 'v2', ''),
        ('user2', False, [{'a': 1}, {'b': 2}], 'v2', 'v3', '+123'),
    ]

    c8y.get = AsyncMock(side_effect=[{'users': jsons}, {'users': []}])
    result = await api.get_all(as_values='enabled')
    assert result == [
        True,
        False,
    ]
