# Copyright (c) 2025 Cumulocity GmbH

import itertools
from contextlib import suppress
from datetime import datetime, timedelta
import json
import os
from unittest.mock import Mock, patch, AsyncMock
from urllib.parse import unquote_plus, urlencode

import pytest

from pyc8y.auth import BasicAuth
from pyc8y.client import CumulocityClient
# from pyc8y.client import CumulocityClient
# from pyc8y.auth import BasicAuth
from pyc8y.model.measurement import Measurement, Measurements, Series

from tests.utils import isolate_last_call_arg


def test_measurement_parsing():
    """Verify that parsing of a Measurement works as expected."""
    measurement_json = {
        'id': '12345',
        'self': 'https://...',
        'type': 'c8y_Measurement',
        'source': {'id': '54321', 'self': 'https://...'},
        'time': '2020-12-31T22:33:44,567Z',
        'c8y_Measurement': {'c8y_temperature': {'unit': 'x', 'value': 12.3}}
    }
    m = Measurement.from_json(measurement_json)

    assert m.id == '12345'
    assert m.source == '54321'
    assert m.type == 'c8y_Measurement'
    assert m.time == '2020-12-31T22:33:44,567Z'
    assert m["c8y_Measurement.c8y_temperature.value"] == 12.3

    assert m.json == measurement_json


def test_measurement_serialization():
    """Verify that serialization of a Measurement works as expected."""
    m = Measurement(
        type="c8y_TestType",
        source="12345",
        time="2020-12-31T22:33:44Z",
        series=[
            ("fragment.series", 1, "#"),
            ("fragment.series2", 2),
        ],
        fragment = {"series3": {"value": 3}}
    )
    assert m.json["fragment"] == {
        "series": {"value": 1, "unit": "#"},
        "series2": {"value": 2},
        "series3": {"value": 3}
    }


async def test_measurement_parsing_as_values():
    """Verify that parsing Measurements directly as values works as expected."""
    measurements_json = {
        'measurements': [
            {
                'id': '12345',
                'self': 'https://...',
                'type': 'c8y_Measurement',
                'source': {'id': '54321', 'self': 'https://...'},
                'time': '2020-12-31T22:33:44,567Z',
                'c8y_Measurement': {'c8y_temperature': {'unit': 'x', 'value': 12.3}}
            }, {
                'id': '12346',
                'self': 'https://...',
                'type': 'c8y_Measurement',
                'source': {'id': '54321', 'self': 'https://...'},
                'time': '2020-12-31T22:33:44,568Z',
                'c8y_Measurement': {'c8y_temperature': {'unit': 'x', 'value': 34.5}}
            }
        ]
    }
    c8y = CumulocityClient(base_url='base', tenant_id='t12345', auth=BasicAuth("user", "pass"))
    c8y.get = AsyncMock(side_effect=(measurements_json, {'measurements': []}))
    result = await c8y.measurements.get_all(as_values=['id', 'type', 'time', 'c8y_Measurement.c8y_temperature.value'])

    assert result == [
        ('12345', 'c8y_Measurement', '2020-12-31T22:33:44,567Z', 12.3),
        ('12346', 'c8y_Measurement', '2020-12-31T22:33:44,568Z', 34.5),
    ]


async def isolate_call_url(fun, **kwargs):
    """Call an Applications API function and isolate the request URL for further assertions."""
    c8y = CumulocityClient(base_url='some.host.com', tenant_id='t123', auth=BasicAuth('user', 'pass'))
    c8y.get = AsyncMock(side_effect=[{'measurements': x, 'statistics': {'totalPages': 1}} for x in ([{}], [])])
    c8y.delete = AsyncMock(return_value={'measurements': [], 'statistics': {'totalPages': 1}})
    with patch('pyc8y.model.Measurement.from_json') as parse_mock:
        parse_mock.return_value = Measurement()
        await fun(c8y.measurements, **kwargs)
    resource = isolate_last_call_arg(c8y.get, 'resource', 0) if c8y.get.called else None
    resource = resource or (isolate_last_call_arg(c8y.delete, 'resource', 0) if c8y.delete.called else None)
    with suppress(KeyError):
        params = None
        params = isolate_last_call_arg(c8y.get, 'params', 1) if c8y.get.called else None
        params = params or (isolate_last_call_arg(c8y.delete, 'params', 1) if c8y.delete.called else None)
    return unquote_plus(resource) if not params else f"{resource}?{urlencode(params)}"


@pytest.mark.parametrize('fun', [
    Measurements.get_all,
    Measurements.get_last,
    Measurements.delete_by,
])
@pytest.mark.parametrize('params, expected, not_expected', [
    ({'expression': "X&Y='A''s B'", 'type': 'T'}, ["?X&Y='A''s B'"], ['type']),
    ({'type': 'T', 'source': 'S'},
     ['type=T', 'source=S'],
     []),
    ({'value_fragment_type': 'T', 'value_fragment_series': 'S'},
     ['valueFragmentType=T', 'valueFragmentSeries=S'],
     ['_']),
    ({'series': 'T.S'},
     ['valueFragmentType=T', 'valueFragmentSeries=S'],
     ['series']),
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
    'expression',
    'type+source',
    'type+series',
    'series',
    'date_from+date_to',
    'after+before',
    'min_age+max_age',
    'kwargs',
])
async def test_select(fun, params, expected, not_expected):
    """Verify that the select function's parameters are processed as expected."""
    if fun is Measurements.get_last:
        params = {k: v for k, v in params.items() if k not in ['date_from', 'after', 'max_age']}
        expected = list(filter(lambda x: 'dateFrom' not in x, expected))
    resource = await isolate_call_url(fun, **params)
    for e in expected:
        assert e in resource
    for ne in not_expected:
        assert ne not in resource


@pytest.mark.parametrize('fun', [
    Measurements.get_all,
    Measurements.delete_by,
])
@pytest.mark.parametrize('args, errors', [
    # date priorities
    (['date_from', 'after'], ['date_from', 'after', 'max_age']),
    (['date_from', 'max_age'], ['date_from', 'after', 'max_age']),
    (['date_to', 'before'], ['date_to', 'before', 'min_age']),
    (['date_to', 'min_age'], ['date_to', 'before', 'min_age']),
], ids=[
    "date_from+after",
    'date_from+max_age',
    'date_to+before',
    'date_to+min_age',
])
async def test_select_invalid_combinations(fun, args, errors):
    """Verify that invalid query filter combinations are raised as expected."""
    with pytest.raises(ValueError) as error:
        params = {x: x.upper() for x in args}
        await isolate_call_url(fun, **params)
    assert all(e in str(error) for e in errors)

@pytest.mark.parametrize('params, expected, not_expected', [
    ({'expression': 'X&Y'}, ['X&Y'], ['expression']),
    ({'source': 'SOURCE'}, ['source=SOURCE'], []),
    ({'series': 'SERIES'}, ['series=SERIES'], []),
    ({'series': ['A', 'B']}, ['series=A', 'series=B'], ['source', ',']),
    ({'aggregation': 'A'}, ['aggregationType=A'], ['series=']),
    ({'reverse': True}, ['revert=true'], ['reverse']),
    ({'before': '2021-01-31', 'after': '2020-01-31'}, ['dateFrom=2020-01-31', 'dateTo=2021-01-31'], ['source', 'series=']),
    ({'date_from': '2020-01-31', 'date_to': '2021-01-31'}, ['dateFrom=2020-01-31', 'dateTo=2021-01-31'], ['date_to', 'date_from']),
])
async def test_get_series_parameters(params, expected, not_expected):
    """Verify that the get_series function parameters are translated as expected."""
    resource = await isolate_call_url(Measurements.get_series, **params)
    for e in expected:
        assert e in resource
    for e in not_expected:
        assert e not in resource


def generate_series_data() -> tuple:
    """Generate all kinds of combinations of series fragments.

    Returns a tuple of testcases and corresponding testcase ID. Each testcase
    element is again a tuple of a JSON structure (the test data) and a list
    of expected series' names (for assertion).

    We will define 2 sets (A and B) of such test cases (with different fragment
    names), each featuring possible JSON combinations of single and multiple
    series as well as invalid structures (not following the syntax for series).

    Finally, we will create test cases from all possible combinations of the two
    basic sets.

    The tests' ID are generated from the expectation set.
    """

    def generate(fragment):
        level2_single = ({fragment: {'series1': {'value': 1}}},
                         [f'{fragment}.series1'])
        level2_multi = ({fragment: {'series1': {'value': 1}, 'series2': {'value': 2}}},
                        [f'{fragment}.series1', f'{fragment}.series2'])
        level2_invalid = ({fragment: {'series1': {'data': 1}}},
                          [])
        level2_mix1 = ({fragment: {'series1': {'data': 1}, 'series2': {'value': 2}}},
                       [f'{fragment}.series2'])
        level2_mix2 = ({fragment: {'series1': {'value': 1}, 'series2': {'data': 2}}},
                       [f'{fragment}.series1'])
        return [level2_single, level2_multi, level2_invalid, level2_mix1, level2_mix2]

    # generating A and B sets
    a = generate('fragmentA')
    b = generate('fragmentB')

    # collecting combinations of A and B cases
    ab = [({**r[0][0], **r[1][0]}, r[0][1] + r[1][1]) for r in itertools.product(a, b)]

    cases = a + ab
    # id is the beautified expectation, prefixed with a number
    ids = [f'{i}: ' + ','.join(map(lambda x: x.replace('.', '/'), x[1])) for i, x in enumerate(cases)]

    return cases, ids


@pytest.mark.parametrize('testcase', generate_series_data()[0], ids=generate_series_data()[1])
def test_get_series(testcase):
    """Verify that the get_series function works as expected.

    The `get_series` function on a measurement determines and returns the
    names of series defined within a single measurement.
    """
    data = {**testcase[0], 'source': {'id': '1'}}
    m = Measurement.from_json(data)
    assert testcase[1] == m.get_series()


@pytest.fixture(name='sample_series')
def fix_sample_series():
    """Verify that parsing an Operation from JSON works and provide this
    as a fixture for other tests."""
    path = os.path.dirname(__file__) + '/series.json'
    with open(path, encoding='utf-8', mode='rt') as f:
        series_json = json.load(f)

    return Series(series_json)


def test_values_of_single_series(sample_series: Series):
    """values_of returns a flat list aligned with timestamps; missing entries are None."""
    for spec in sample_series.specs:
        values = sample_series.values_of(series=spec.series, value='min')
        assert len(values) == len(sample_series['values'])
        assert all(v is None or isinstance(v, (int, float)) for v in values)


def test_values_of_default_series_when_only_one():
    """values_of can omit `series` when there's exactly one."""
    only_one = Series({
        "series": [{"type": "c8y_T", "name": "T", "unit": "C"}],
        "values": {
            "2026-01-01T00:00:00Z": [{"min": 1.0, "max": 2.0}],
            "2026-01-01T00:01:00Z": [{"min": 3.0, "max": 4.0}],
        },
        "truncated": False,
    })
    assert only_one.values_of(value='min') == [1.0, 3.0]


def test_values_of_default_value_when_only_one():
    """values_of can omit `value` when the series holds exactly one value key."""
    one_value = Series({
        "series": [{"type": "c8y_T", "name": "T", "unit": "C"}],
        "values": {
            "2026-01-01T00:00:00Z": [{"min": 1.0}],
            "2026-01-01T00:01:00Z": [{"min": 3.0}],
        },
        "truncated": False,
    })
    assert one_value.values_of() == [1.0, 3.0]


def test_values_of_requires_series_when_ambiguous(sample_series: Series):
    """Omitting `series` is rejected if multiple series are present."""
    with pytest.raises(ValueError, match="multiple series"):
        sample_series.values_of(value='min')


def test_values_of_requires_value_when_ambiguous(sample_series: Series):
    """Omitting `value` is rejected if the series holds multiple value keys."""
    spec = sample_series.specs[0]
    with pytest.raises(ValueError, match="multiple values"):
        sample_series.values_of(series=spec.series)


def test_values_of_unknown_series(sample_series: Series):
    with pytest.raises(KeyError, match="No such series"):
        sample_series.values_of(series='nope.thing', value='min')


def test_collect_single_value_no_timestamps(sample_series: Series):
    """collect always returns tuples; single value -> [(v,), ...]."""
    spec = sample_series.specs[0]
    result = sample_series.collect(series=spec.series, value='min')
    assert len(result) == len(sample_series['values'])
    assert all(isinstance(t, tuple) and len(t) == 1 for t in result)


def test_collect_single_value_with_timestamps(sample_series: Series):
    """collect with single value + timestamps -> [(ts, v), ...]."""
    spec = sample_series.specs[0]
    result = sample_series.collect(series=spec.series, value='min', timestamps=True)
    assert len(result) == len(sample_series['values'])
    assert all(len(t) == 2 for t in result)
    assert all(isinstance(t[0], str) for t in result)


def test_collect_multi_value(sample_series: Series):
    """collect with a list of values -> tuples one element per value."""
    spec = sample_series.specs[0]
    result = sample_series.collect(series=spec.series, value=['min', 'max'])
    assert all(len(t) == 2 for t in result)


def test_collect_multi_value_with_datetime_timestamps(sample_series: Series):
    """collect with multi values + datetime timestamps -> [(dt, v1, v2), ...]."""
    spec = sample_series.specs[0]
    result = sample_series.collect(series=spec.series, value=['min', 'max'], timestamps='datetime')
    assert all(len(t) == 3 for t in result)
    assert all(isinstance(t[0], datetime) for t in result)


def test_collect_defaults_to_all_value_keys(sample_series: Series):
    """When value is omitted, all available value keys are collected."""
    spec = sample_series.specs[0]
    # determine the actual value keys present in the data
    expected_keys = next(
        row[0].keys() for row in sample_series['values'].values() if row and row[0]
    )
    result = sample_series.collect(series=spec.series)
    assert all(len(t) == len(expected_keys) for t in result)


def test_collect_epoch_timestamps(sample_series: Series):
    """timestamps='epoch' yields float seconds-since-epoch as the prefix."""
    spec = sample_series.specs[0]
    result = sample_series.collect(series=spec.series, value='min', timestamps='epoch')
    assert all(isinstance(t[0], float) for t in result)


def test_collect_preserves_alignment_with_nones(sample_series: Series):
    """Rows where the series has no value yield None entries (not dropped)."""
    spec = sample_series.specs[0]
    result = sample_series.collect(series=spec.series, value='min')
    assert len(result) == len(sample_series['values'])
    # at least one None expected in the sample (the old test asserted Nones existed)
    assert any(t[0] is None for t in result)
