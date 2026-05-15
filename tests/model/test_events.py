# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import unquote_plus

import pytest

from pyc8y.model.event import Events

from tests.utils import isolate_last_call_arg


async def _isolate_call_url(fun, **kwargs):
    """Call an Events API function and isolate the request URL/params for further assertions."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'events': [], 'statistics': {'totalPages': 1}})
    c8y.delete = AsyncMock(return_value={})
    events = Events(c8y=c8y)

    result = fun(events, **kwargs)
    # `select` returns an async iterator; `get_all`/`get_count`/`delete_by` are awaitables
    try:
        # awaitable case
        await result
    except TypeError:
        # async iterator case
        async for _ in result:
            pass

    if c8y.get.called:
        resource = isolate_last_call_arg(c8y.get, 'resource', 0)
        params = c8y.get.call_args.kwargs.get('params') or ()
    elif c8y.delete.called:
        resource = isolate_last_call_arg(c8y.delete, 'resource', 0)
        params = c8y.delete.call_args.kwargs.get('params') or ()
    else:
        return ''

    if params:
        query_string = '&'.join(f'{k}={v}' for k, v in params)
        resource = f'{resource}?{query_string}'
    return unquote_plus(resource)


@pytest.mark.parametrize('fun', [
    Events.get_all,
    Events.get_count,
])
@pytest.mark.parametrize('params, expected, not_expected', [
    ({'expression': 'EX', 'type': 'T'}, ['?EX'], ['type']),
    ({'type': 'T', 'source': 'S', 'fragment': 'F'}, ['type=T', 'source=S', 'fragmentType=F'], []),
    # data priorities
    ({'date_from': '2020-12-31', 'date_to': '2021-12-31'},
     ['dateFrom=2020-12-31', 'dateTo=2021-12-31'],
     []),
    ({'after': '2020-12-31', 'before': '2021-12-31'},
     ['dateFrom=2020-12-31', 'dateTo=2021-12-31'],
     []),
    ({'last_updated_from': '2020-12-31', 'last_updated_to': '2021-12-31'},
     ['lastUpdatedFrom=2020-12-31', 'lastUpdatedTo=2021-12-31'],
     []),
    ({'min_age': timedelta(days=3), 'max_age': timedelta(weeks=1)},
     ['dateFrom', 'dateTo'],
     ['min', 'max']),
    ({'snake_case': 'SC', 'pascalCase': 'PC'},
     ['snakeCase=SC', 'pascalCase=PC'],
     ['_']),

], ids=[
    'expression',
    'type+source+fragment',
    'date_from+date_to',
    'after+before',
    'last_updated_from+last_updated_to',
    'min_age+max_age',
    'kwargs'
])
async def test_select(fun, params, expected, not_expected):
    """Verify that the select function's parameters are processed as expected."""
    resource = await _isolate_call_url(fun, **params)
    for e in expected:
        assert e in resource, f"Expected '{e}' in URL: {resource}"
    for ne in not_expected:
        assert ne not in resource, f"Did not expect '{ne}' in URL: {resource}"


@pytest.mark.parametrize('params, expected, not_expected', [
    ({'asc': True}, ['revert=true'], ['reverse', 'asc']),
    ({'asc': False}, ['revert=false'], ['reverse', 'asc']),
    ({'revert': True}, ['revert=true'], ['reverse']),
    # revert wins when both supplied
    ({'asc': True, 'revert': False}, ['revert=false'], ['reverse']),
])
async def test_select_ordering(params, expected, not_expected):
    """Verify `asc` / `revert` translate to the server's `revert` correctly on Events."""
    resource = await _isolate_call_url(Events.get_all, **params)
    for e in expected:
        assert e in resource, f"Expected '{e}' in URL: {resource}"
    for ne in not_expected:
        assert ne not in resource, f"Did not expect '{ne}' in URL: {resource}"


@pytest.mark.parametrize('params, expected, not_expected', [
    ({'expression': 'EX', 'type': 'T'}, ['?EX'], ['type']),
    ({'type': 'T', 'source': 'S', 'fragment': 'F'}, ['type=T', 'source=S', 'fragmentType=F'], []),
    ({'date_from': '2020-12-31', 'date_to': '2021-12-31'},
     ['dateFrom=2020-12-31', 'dateTo=2021-12-31'],
     []),
], ids=[
    'expression',
    'type+source+fragment',
    'date_from+date_to',
])
async def test_delete_by(params, expected, not_expected):
    """Verify that the delete_by function's parameters are properly serialized."""
    resource = await _isolate_call_url(Events.delete_by, **params)
    for e in expected:
        assert e in resource, f"Expected '{e}' in URL: {resource}"
    for ne in not_expected:
        assert ne not in resource, f"Did not expect '{ne}' in URL: {resource}"


@pytest.mark.parametrize('fun', [
    Events.get_all,
    Events.get_count,
    Events.delete_by,
])
@pytest.mark.parametrize('args, errors', [
    # date priorities
    (['date_from', 'after'], ['date_from', 'after', 'max_age']),
    (['date_from', 'max_age'], ['date_from', 'after', 'max_age']),
    (['date_to', 'before'], ['date_to', 'before', 'min_age']),
    (['date_to', 'min_age'], ['date_to', 'before', 'min_age']),
    (['created_from', 'created_after'], ['created_from', 'created_after']),
    (['created_to', 'created_before'], ['created_to', 'created_before']),
    (['last_updated_from', 'updated_after'], ['last_updated_from', 'updated_after']),
    (['last_updated_to', 'updated_before'], ['last_updated_to', 'updated_before']),
    (['with_source_assets'], ['source']),
    (['with_source_devices'], ['source']),
], ids=[
    "date_from+after",
    'date_from+max_age',
    'date_to+before',
    'date_to+min_age',
    'created_from+created_before',
    'created_to+created_after',
    'updated_from+updated_before',
    'updated_to+updated_after',
    'with_source_assets',
    'with_source_devices',
])
async def test_select_invalid_combinations(fun, args, errors):
    """Verify that invalid query filter combinations are raised as expected."""
    with pytest.raises(ValueError) as error:
        params = {x: x.upper() for x in args}
        await _isolate_call_url(fun, **params)
    assert all(e in str(error) for e in errors)


async def test_select_as_values():
    """Verify that select as values works as expected."""
    jsons = [
        {'type': 'type1', 'text': 'text1', 'source': 'source1', 'test_Fragment': {'key': 'value1', 'key2': 'value2'}},
        {'type': 'type2', 'text': 'text2', 'source': 'source2', 'test_Fragment': {'key': 'value2'}},
    ]

    api = Events(c8y=MagicMock())
    api.c8y.get = AsyncMock(side_effect=[{'events': jsons}, {'events': []}])
    result = await api.get_all(as_values=['type', 'text', 'test_Fragment.key', 'test_Fragment.key2'])
    assert result == [
        ('type1', 'text1', 'value1', 'value2'),
        ('type2', 'text2', 'value2', None),
    ]

    api.c8y.get = AsyncMock(side_effect=[{'events': jsons}, {'events': []}])
    result = await api.get_all(as_values=['type', 'text', 'test_Fragment.key', ('test_Fragment.key2', '-')])
    assert result == [
        ('type1', 'text1', 'value1', 'value2'),
        ('type2', 'text2', 'value2', '-'),
    ]
