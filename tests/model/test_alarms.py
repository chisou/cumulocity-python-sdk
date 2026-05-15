# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import unquote_plus

import pytest

from pyc8y.model.alarm import Alarm, Alarms

from tests.utils import isolate_last_call_arg


async def _isolate_call_url(fun, **kwargs):
    """Call an Alarms API function and isolate the request URL/params for further assertions."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'alarms': [], 'statistics': {'totalPages': 1}})
    c8y.put = AsyncMock(return_value={})
    c8y.delete = AsyncMock(return_value={})
    alarms = Alarms(c8y=c8y)

    if fun is Alarms.apply_by:
        result = fun(alarms, Alarm(), **kwargs)
    else:
        result = fun(alarms, **kwargs)

    # `select` returns an async iterator; the rest are awaitables
    try:
        await result
    except TypeError:
        async for _ in result:
            pass

    if c8y.get.called:
        mock = c8y.get
    elif c8y.put.called:
        mock = c8y.put
    elif c8y.delete.called:
        mock = c8y.delete
    else:
        return ''

    resource = isolate_last_call_arg(mock, 'resource', 0)
    params = mock.call_args.kwargs.get('params') or ()
    if params:
        query_string = '&'.join(f'{k}={v}' for k, v in params)
        sep = '&' if '?' in resource else '?'
        resource = f'{resource}{sep}{query_string}'
    return unquote_plus(resource)


@pytest.mark.parametrize('fun', [
    Alarms.get_all,
    Alarms.count,
    Alarms.apply_by,
    Alarms.delete_by,
])
@pytest.mark.parametrize('params, expected, not_expected', [
    ({'type': 'T', 'source': 'S', 'fragment': 'F'}, ['type=T', 'source=S', 'fragmentType=F'], []),
    ({'status': 'ST', 'severity': 'SE', 'resolved': False}, ['status=ST', 'severity=SE', 'resolved=false'], []),
    # data priorities
    ({'date_from': '2020-12-31', 'date_to': '2021-12-31'},
     ['dateFrom=2020-12-31', 'dateTo=2021-12-31'],
     []),
    ({'after': '2020-12-31', 'before': '2021-12-31'},
     ['dateFrom=2020-12-31', 'dateTo=2021-12-31'],
     []),
    ({'min_age': timedelta(days=3), 'max_age': timedelta(weeks=1)},
     ['dateFrom', 'dateTo'],
     ['min', 'max']),
    ({'snake_case': 'SC', 'pascalCase': 'PC'},
     ['snakeCase=SC', 'pascalCase=PC'],
     ['_']),

], ids=[
    'type+source+fragment',
    'status+severity+resolved',
    'date_from+date_to',
    'after+before',
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


@pytest.mark.parametrize('fun', [
    Alarms.get_all,
    Alarms.count,
    Alarms.delete_by,
])
async def test_select_expression(fun):
    """Verify that the `expression` parameter is forwarded into the URL,
    and that other filter args are ignored when an expression is set."""
    resource = await _isolate_call_url(fun, expression='EX', type='T')
    assert '?EX' in resource, f"Expected '?EX' in URL: {resource}"
    assert 'type' not in resource, f"Did not expect 'type' in URL: {resource}"


@pytest.mark.parametrize('fun', [
    Alarms.get_all,
    Alarms.delete_by,
])
@pytest.mark.parametrize('params, expected', [
    ({'created_from': '2020-12-31', 'created_to': '2021-12-31'},
     ['createdFrom=2020-12-31', 'createdTo=2021-12-31']),
], ids=[
    'created_from+created_to',
])
async def test_select_created(fun, params, expected):
    """Verify that the created_* parameters are processed.

    Note: `count` and `apply_by` don't accept created_*/updated_* in pyc8y.
    """
    resource = await _isolate_call_url(fun, **params)
    for e in expected:
        assert e in resource, f"Expected '{e}' in URL: {resource}"


@pytest.mark.parametrize('fun', [
    Alarms.get_all,
    Alarms.delete_by,
])
@pytest.mark.parametrize('params, expected', [
    ({'last_updated_from': '2020-12-31', 'last_updated_to': '2021-12-31'},
     ['lastUpdatedFrom=2020-12-31', 'lastUpdatedTo=2021-12-31']),
], ids=[
    'last_updated_from+last_updated_to',
])
async def test_select_last_updated(fun, params, expected):
    """Verify that the last_updated_* parameters are processed.

    Note: `count` and `apply_by` don't accept last_updated_*/updated_* in pyc8y.
    """
    resource = await _isolate_call_url(fun, **params)
    for e in expected:
        assert e in resource, f"Expected '{e}' in URL: {resource}"


async def test_select_page_size():
    """`page_size` is forwarded as `pageSize` on `get_all`/`select`."""
    resource = await _isolate_call_url(Alarms.get_all, page_size=8)
    assert 'pageSize=8' in resource, f"Expected 'pageSize=8' in URL: {resource}"


async def test_select_as_values():
    """Verify that select as values works as expected."""
    jsons = [
        {'type': 'type1', 'text': 'text1', 'source': 'source1', 'test_Fragment': {'key': 'value1', 'key2': 'value2'}},
        {'type': 'type2', 'text': 'text2', 'source': 'source2', 'test_Fragment': {'key': 'value2'}},
    ]

    api = Alarms(c8y=MagicMock())
    api.c8y.get = AsyncMock(side_effect=[{'alarms': jsons}, {'alarms': []}])
    result = await api.get_all(as_values=['type', 'text', 'test_Fragment.key', 'test_Fragment.key2'])
    assert result == [
        ('type1', 'text1', 'value1', 'value2'),
        ('type2', 'text2', 'value2', None),
    ]

    api.c8y.get = AsyncMock(side_effect=[{'alarms': jsons}, {'alarms': []}])
    result = await api.get_all(as_values=['type', 'text', 'test_Fragment.key', ('test_Fragment.key2', '-')])
    assert result == [
        ('type1', 'text1', 'value1', 'value2'),
        ('type2', 'text2', 'value2', '-'),
    ]


@pytest.mark.parametrize('fun', [
    Alarms.get_all,
    Alarms.count,
    Alarms.apply_by,
    Alarms.delete_by,
])
@pytest.mark.parametrize('args, errors', [
    # date priorities
    (['date_from', 'after'], ['date_from', 'after', 'max_age']),
    (['date_from', 'max_age'], ['date_from', 'after', 'max_age']),
    (['date_to', 'before'], ['date_to', 'before', 'min_age']),
    (['date_to', 'min_age'], ['date_to', 'before', 'min_age']),
    (['with_source_assets'], ['source']),
    (['with_source_devices'], ['source']),
], ids=[
    "date_from+after",
    'date_from+max_age',
    'date_to+before',
    'date_to+min_age',
    'with_source_assets',
    'with_source_devices',
])
async def test_select_invalid_combinations(fun, args, errors):
    """Verify that invalid query filter combinations are raised as expected."""
    with pytest.raises(ValueError) as error:
        params = {x: x.upper() for x in args}
        await _isolate_call_url(fun, **params)
    assert all(e in str(error) for e in errors)


@pytest.mark.parametrize('fun', [
    Alarms.get_all,
    Alarms.delete_by,
])
@pytest.mark.parametrize('args, errors', [
    (['created_from', 'created_after'], ['created_from', 'created_after']),
    (['created_to', 'created_before'], ['created_to', 'created_before']),
], ids=[
    'created_from+created_after',
    'created_to+created_before',
])
async def test_select_invalid_created_combinations(fun, args, errors):
    """Verify that invalid `created_*` combinations raise as expected.

    Note: `count` and `apply_by` don't accept created_* in pyc8y.
    """
    with pytest.raises(ValueError) as error:
        params = {x: x.upper() for x in args}
        await _isolate_call_url(fun, **params)
    assert all(e in str(error) for e in errors)


@pytest.mark.parametrize('fun', [
    Alarms.get_all,
    Alarms.delete_by,
])
@pytest.mark.parametrize('args, errors', [
    (['last_updated_from', 'updated_after'], ['last_updated_from', 'updated_after']),
    (['last_updated_to', 'updated_before'], ['last_updated_to', 'updated_before']),
], ids=[
    'updated_from+updated_after',
    'updated_to+updated_before',
])
async def test_select_invalid_updated_combinations(fun, args, errors):
    """Verify that invalid `updated_*`/`last_updated_*` combinations raise as expected.

    Note: `count` and `apply_by` don't accept updated_*/last_updated_* in pyc8y.
    """
    with pytest.raises(ValueError) as error:
        params = {x: x.upper() for x in args}
        await _isolate_call_url(fun, **params)
    assert all(e in str(error) for e in errors)
