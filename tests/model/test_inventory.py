# Copyright (c) 2025 Cumulocity GmbH
# pylint: disable=protected-access

from unittest.mock import Mock

import pytest

from pyc8y.model import ManagedObject
from pyc8y.model.inventory import Inventory
from pyc8y.base_util import encode_odata_query_value


@pytest.mark.parametrize(
    "test, expected", [("string", "string"), ("with spaces", "with spaces"), ("quote's", "quote''s")]
)
def test_encode_odata_query_value(test, expected):
    """Verify that the query value encoding works as expected."""
    assert encode_odata_query_value(test) == expected


@pytest.mark.parametrize(
    "specified, expected",
    [
        (["query"], ["query"]),  # query short-circuits everything
        (["query", "with"], ["query", "with"]),
        (["query", "type", "with"], ["query", "with"]),  # type ignored when query set
        (["type", "with"], ["type", "with"]),
        (["owner", "with"], ["owner", "with"]),
        (["text", "with", "with2"], ["text", "with", "with2"]),
        (["fragment", "with"], ["fragment", "with"]),
        (["fragments"], ["fragment"]),  # single fragment via fragments= -> fast path (fragment=)
        (["fragments", "with"], ["fragment", "with"]),
        (["name", "with"], ["query", "with"]),  # name forces query
        (["fragments", "fragment"], ["fragment"]),  # only one of fragment/fragments is used
        (["name", "order_by"], ["query"]),  # order_by forces query
        (["fragments", "name"], ["query"]),  # name forces query
        (["text", "name", "owner", "type", "order_by"], ["query"]),  # name+order_by force query
        (["text", "owner", "type", "fragment"], ["text", "owner", "type", "fragment"]),
    ],
)
def test_collect_query_params(specified, expected):
    """Verify that query parameters are assembled correctly."""

    obj = Mock(_object_type=ManagedObject)

    kwargs = {x: x.upper() for x in specified}
    params = Inventory._collate_filter_params(obj, **kwargs)
    assert params.keys() == set(expected)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"fragments": ["A", "B"]}, ["query", "has(A)", "has(B)"]),  # multiple fragments force query
        ({"fragments": ["A", "B"], "with": "W"}, ["query", "with", "has(A)", "has(B)"]),
        ({"fragments": ["A"]}, ["fragment"]),  # 1-element list still fast path
        ({"fragment": "A", "fragments": ["B", "C"]}, ["query", "has(B)", "has(C)"]),  # mix: fragment ignored
    ],
)
def test_collect_query_params_multi_fragments(kwargs, expected):
    """Verify fragments-list handling: single -> fast path, multiple -> OData query."""

    obj = Mock(_object_type=ManagedObject)

    params = Inventory._collate_filter_params(obj, **kwargs)
    params_string = "|".join(params.keys() | params.values())
    assert all(x in params_string for x in expected)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        # filter-clause encoding (slow path)
        ({"parent": "P"}, ["bygroupid(P)"]),
        ({"name": "N"}, ["name eq 'N'"]),
        ({"name": "Bob's"}, ["name eq 'Bob''s'"]),
        ({"name": "N", "type": "T"}, ["name eq 'N'", "type eq T"]),
        ({"name": "N", "owner": "admin"}, ["name eq 'N'", "owner eq admin"]),
        ({"name": "N", "text": "hello world"}, ["name eq 'N'", "text eq 'hello world'"]),
        ({"name": "N", "text": "it's"}, ["name eq 'N'", "text eq 'it''s'"]),
        ({"parent": "P", "fragments": ["A", "B"]}, ["bygroupid(P)", "has(A)", "has(B)"]),
        ({"parent": "P", "fragment": "F"}, ["bygroupid(P)", "has(F)"]),
        # multiple clauses joined with `and`
        ({"name": "N", "type": "T", "owner": "O"}, ["name eq 'N'", "type eq T", "owner eq O", " and "]),
        # order_by emitted as +$orderby= suffix
        ({"name": "N", "order_by": "creationTime asc"}, ["name eq 'N'", "+$orderby=creationTime asc"]),
        # caller-provided pre-built filters are preserved
        ({"name": "N", "filters": ["custom eq 42"]}, ["name eq 'N'", "custom eq 42"]),
    ],
    ids=[
        "parent",
        "name-quoted",
        "name-single-quote-escaped",
        "type-unquoted",
        "owner-unquoted",
        "text-quoted",
        "text-single-quote-escaped",
        "parent+multi-fragments",
        "parent+single-fragment",
        "multiple-clauses-and-joined",
        "order_by-suffix",
        "pre-built-filters-merged",
    ],
)
def test_odata_query_clauses(kwargs, expected):
    """Verify OData filter-clause assembly in the slow-path query value."""
    obj = Mock(_object_type=ManagedObject)
    params = Inventory._collate_filter_params(obj, **kwargs)
    query = params.get("query", "")
    for clause in expected:
        assert clause in query, f"missing clause {clause!r} in {query!r}"
