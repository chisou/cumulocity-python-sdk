# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris

# pylint: disable=protected-access

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock

from deepdiff import DeepDiff
import pytest

from pyc8y.model.model_base import CumulocityObject, CumulocityResource, resolve_page_size
from pyc8y.model.model_util import as_record, as_tuple, get_by


@pytest.mark.parametrize("value", ["new_value", "", True, False, 0, -1, 12, [1, 2, 3], [], {"a": 1}, {"a": {"b": 1}}, {}, None])
@pytest.mark.parametrize("path", [
    "string1",
    "string2",
    "new_attribute",
    "integer1",
    "integer2",
    "boolean1",
    "boolean2",
    "fragmentA.key",
    "fragmentB.key2",
    "fragmentA",
    "fragmentB.new_key",
    "fragmentC.new_key",
])
@pytest.mark.parametrize("mode", ["function", "item"])
def test_set(mode, path, value):
    source_json = {
        "string1": "value",
        "string2": "",
        "integer1": 12,
        "integer2": 0,
        "boolean1": True,
        "boolean2": False,
        "fragmentA": {"key": "value"},
        "fragmentB": {"key1": "value1", "key2": "value2"},
    }
    obj = CumulocityObject.from_json(deepcopy(source_json))

    if mode == "function":
        obj.set(path, value)
    elif mode == "item":
        obj[path] = value

    new_json = obj.json
    updated_json = obj._staged_json

    # -> new value is set in JSON
    assert get_by(new_json, path) == value

    # -> in updated JSON as well
    assert get_by(updated_json, path) == value

    # -> rest of source is not part of update JSON
    level0 = path.split(".")[0]
    assert updated_json.keys() == {level0}

    # -> entire branch is copied to update JSON
    #    (only for fragment changes)
    if level0 in source_json and level0.startswith("fragment"):
        diff = DeepDiff(
            source_json[level0],
            updated_json[level0],
        )
        # -> there is exactly 1 value change diff
        #    (value changed, item added, type/value changed, item removed)
        assert len(diff) == 1


@pytest.mark.parametrize("json, path, default, expected", [
    ({}, "some", None, None),
    ({'a': 1}, 'a', 'x', 1),
    ({'x': 1}, 'a', 1, 1),
    ({'a': 1, 'b': 2}, 'b', None, 2),
    ({'a': {'b': 1, 'c': 2}, 'm': '3'}, 'a.b', None, 1),
    ({'a': {'b': 1, 'c': 2}, 'm': '3'}, 'a.c', None, 2),
    ({'a': {'b': 1, 'c': 2}, 'm': 3}, 'm', None, 3),
    ({'a': {'b': 1, 'c': 2}, 'm': 3}, 'a.d', 4, 4),
])
def test_get_by(json, path, default, expected):
    """Verify that get by path works as expected."""
    assert get_by(json, path, default) == expected


@pytest.mark.parametrize("limit, page_size, include, exclude, expected_page_size", [
    (None, None, None, None, 100),
    (5, None, None, None, 5),
    (5, 50, None, None, 50),
    (None, 200, None, None, 200),
    (5, None, "x", None, 100),
    (5, None, None, "x", 100),
    (5, 50, "x", None, 50),
], ids=[
    "All None -> default",
    "Limit only, no filter -> match limit",
    "Explicit page_size wins",
    "page_size set, no limit",
    "Limit + include -> default",
    "Limit + exclude -> default",
    "Explicit page_size wins even with filter",
])
def test_resolve_page_size(limit, page_size, include, exclude, expected_page_size):
    """Verify that page_size is resolved according to the rules."""
    assert resolve_page_size(page_size, limit, include, exclude) == expected_page_size


@pytest.mark.parametrize("paths, expected", [
    (['x'], (None,)),
    (['a'], (1,)),
    (['bb.b1'], (True,)),
    (['bb.b2'], (False,)),
    (['ccc.c1'], ([],)),
    (['ccc.c2'], ([1, 2, 3],)),
    (['ccc.c3'], (None,)),
    (['snake_case'], ('v',)),
    (['pascalCase'], ('v',)),
    (['pascal_case'], ('v',)),
    (['mixed_case.caseMixed'], ('v',)),
    (['mixed_case.case_mixed'], ('v',)),
    (['a', 'bb.b1', 'ccc.c2'], (1, True, [1, 2, 3])),
    (['bb.b2', 'ccc.c3'], (False, None)),
    (['a', 'bb.b3', 'ccc.c2'], (1, None, [1, 2, 3])),
    (['a', ('bb.b3', '-'), 'ccc.c2'], (1, '-', [1, 2, 3])),

], ids=[
    'none',
    'int',
    'nested_True',
    'nested_False',
    'nested_empty',
    'nested_list',
    'nested_None',
    'snake_case',
    'pascal_case_1',
    'pascal_case_2',
    'mixed_case_1',
    'mixed_case_2',
    'multi_1',
    'multi_2',
    'multi_default_1',
    'multi_default_2',
])
def test_as_tuples(paths, expected):
    """Verify that the as_tuple function works as expected."""
    json = {
        # types
        'a': 1,
        'bb': {
            'b1': True,
            'b2': False},
        'ccc': {
            'c1': [],
            'c2': [1, 2, 3],
            'c3': None,
        },
        'snake_case': 'v',
        'pascalCase': 'v',
        'mixed_case': {'caseMixed': 'v'}
    }

    assert as_tuple(json, paths) == expected


@pytest.mark.parametrize("mapping, expected", [
    ({'r': 'x'}, {'r': None}),
    ({'r': 'a'}, {'r': 1}),
    ({'r': ('x', '-')}, {'r': '-'}),
    ({'r': 'bb.b1'}, {'r': True}),
    ({'r': 'bb.b2'}, {'r': False}),
    ({'r': 'ccc.c1'}, {'r': []}),
    ({'r': 'ccc.c2'}, {'r': [1, 2, 3]}),
    ({'r': 'ccc.c3'}, {'r': None}),
    ({'r': 'snake_case'}, {'r': 'v'}),
    ({'r': 'pascalCase'}, {'r': 'v'}),
    ({'r': 'pascal_case'}, {'r': 'v'}),
    ({'r': 'mixed_case.caseMixed'}, {'r': 'v'}),
    ({'r': 'mixed_case.case_mixed'}, {'r': 'v'}),
    ({'r': 'a', 's': 'bb.b1', 't': 'ccc.c2'}, {'r': 1, 's': True, 't': [1, 2, 3]}),
    ({'r': 'bb.b2', 's': 'ccc.c3'}, {'r': False, 's': None}),
    ({'r': 'a', 's': 'bb.b3', 't': 'ccc.c2'}, {'r': 1, 's': None, 't': [1, 2, 3]}),
    ({'r': 'a', 's': ('bb.b3', '-'), 't': 'ccc.c2'}, {'r': 1, 's': '-', 't': [1, 2, 3]}),

], ids=[
    'none',
    'int',
    'default',
    'nested_True',
    'nested_False',
    'nested_empty',
    'nested_list',
    'nested_None',
    'snake_case',
    'pascal_case_1',
    'pascal_case_2',
    'mixed_case_1',
    'mixed_case_2',
    'multi_1',
    'multi_2',
    'multi_default_1',
    'multi_default_2',
])
def test_as_record(mapping, expected):
    """Verify that the as_record function works as expected."""
    json = {
        # types
        'a': 1,
        'bb': {
            'b1': True,
            'b2': False},
        'ccc': {
            'c1': [],
            'c2': [1, 2, 3],
            'c3': None,
        },
        'snake_case': 'v',
        'pascalCase': 'v',
        'mixed_case': {'caseMixed': 'v'}
    }

    assert as_record(json, mapping) == expected


def test_object_parsing():
    """Verify that complex object parsing works as expected."""

    obj_json = {
        'id': 'some id',
        'self': 'some reference',
        'c8y_field': 'field data',
        'c8y_fixed': 12,
        'c8y_simple': 'simple attribute like fragment',
        'c8y_complex': {'field': 'value'}
    }

    # parsing the object JSON into a new object instance
    parsed_obj = CumulocityObject.from_json(obj_json)

    # -> all standard properties are set
    assert parsed_obj.id == obj_json['id']
    assert parsed_obj['c8y_field'] == obj_json['c8y_field']
    assert parsed_obj['c8y_fixed'] == obj_json['c8y_fixed']
    # -> all fragments are set
    assert parsed_obj['c8y_simple'] == obj_json['c8y_simple']
    assert parsed_obj['c8y_complex.field'] == obj_json['c8y_complex']['field']
    # -> no update should be recorded
    assert not parsed_obj._staged_json


def test_object_instantiation_and_formatting():
    """Verify that complex object instantiation, basic access and JSON
    export works as expected."""

    # 1) when using the constructor and standard functions, the
    # write access is not recorded (it is in pyc8y's model — kwargs are staged)
    obj = CumulocityObject(
        field='field value',
        fixed_field=123,
        simple=True,
        complex={'a': 'valueA', 'b': 'valueB'},
        additionalField=True,
        additionalFragment={'value1': "A", 'value2': "B"}
    )

    # -> all standard properties are set
    assert obj.id is None
    assert obj['field'] == 'field value'
    assert obj['fixed_field'] == 123
    # -> all fragments are set
    assert obj['simple'] is True
    assert obj['complex.a'] == 'valueA'
    assert obj['complex.b'] == 'valueB'
    assert obj['additionalField'] is True
    assert obj['additionalFragment.value1'] == 'A'
    assert obj['additionalFragment.value2'] == 'B'


async def test_iteration():
    """Verify that iteration works as expected."""
    page_size = 10
    num_all = 100
    limit = 100
    expected = 100

    all_items = [{'i': i} for i in range(num_all)]

    # returns a 'page' from all items
    async def fetch_page(page, **_):
        s = page_size * (page - 1)
        e = page_size * page
        return all_items[s:e]

    # create class under test
    res = CumulocityResource(MagicMock())
    res._object_type = CumulocityObject
    res._fetch_page = AsyncMock(side_effect=fetch_page)

    # iterate over results
    result_ids = []
    async for x in res._iterate(
        expression=None,
        params=None,
        page_number=None,
        limit=limit,
        include=None,
        exclude=None,
    ):
        result_ids.append(x._source_json['i'])

    # check expectation
    assert result_ids == list(range(expected))
