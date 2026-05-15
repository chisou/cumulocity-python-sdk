# Copyright (c) 2025 Cumulocity GmbH

from datetime import datetime, timedelta, timezone

import pytest

from pyc8y.model.model_base import map_params


td = timedelta
dt = datetime
UTC = timezone.utc


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        # passthrough & camelCasing
        ({"type": "X"},                                              [("type", "X")]),
        ({"source": "S"},                                            [("source", "S")]),
        ({"name": "N"},                                              [("name", "N")]),
        ({"bulk_id": "B"},                                           [("bulkOperationId", "B")]),
        ({"unknown_kwarg": "v"},                                     [("unknownKwarg", "v")]),
        ({"pascalCase": "v"},                                        [("pascalCase", "v")]),

        # named parameters that get renamed
        ({"fragment": "f"},                                          [("fragmentType", "f")]),
        ({"reverse": True},                                          [("revert", "true")]),

        # date params: short forms renamed, long forms camelCased
        ({"before": "2026-01-01T00:00:00+00:00"},                    [("dateTo",   "2026-01-01T00:00:00.000Z")]),
        ({"after":  "2026-01-01T00:00:00+00:00"},                    [("dateFrom", "2026-01-01T00:00:00.000Z")]),
        ({"date_to":   "2026-01-01T00:00:00+00:00"},                 [("dateTo",   "2026-01-01T00:00:00.000Z")]),
        ({"date_from": "2026-01-01T00:00:00+00:00"},                 [("dateFrom", "2026-01-01T00:00:00.000Z")]),
        ({"created_before": "2026-01-01T00:00:00+00:00"},            [("createdTo",   "2026-01-01T00:00:00.000Z")]),
        ({"created_after":  "2026-01-01T00:00:00+00:00"},            [("createdFrom", "2026-01-01T00:00:00.000Z")]),
        ({"created_to":     "2026-01-01T00:00:00+00:00"},            [("createdTo",   "2026-01-01T00:00:00.000Z")]),
        ({"created_from":   "2026-01-01T00:00:00+00:00"},            [("createdFrom", "2026-01-01T00:00:00.000Z")]),
        ({"updated_before": "2026-01-01T00:00:00+00:00"},            [("lastUpdatedTo",   "2026-01-01T00:00:00.000Z")]),
        ({"updated_after":  "2026-01-01T00:00:00+00:00"},            [("lastUpdatedFrom", "2026-01-01T00:00:00.000Z")]),
        ({"last_updated_to":   "2026-01-01T00:00:00+00:00"},         [("lastUpdatedTo",   "2026-01-01T00:00:00.000Z")]),
        ({"last_updated_from": "2026-01-01T00:00:00+00:00"},         [("lastUpdatedFrom", "2026-01-01T00:00:00.000Z")]),

        # datetime objects get formatted to ISO with Z
        ({"date_from": dt(2026, 1, 1, tzinfo=UTC)},                  [("dateFrom", "2026-01-01T00:00:00.000Z")]),

        # value encoding
        ({"reverse": False},                                         [("revert", "false")]),

        # sequence expansion
        ({"series": "A"},                                            [("series", "A")]),
        ({"series": ["A", "B"]},                                     [("series", "A"), ("series", "B")]),
        ({"aggregation_function": "min"},                            [("aggregationFunction", "min")]),
        ({"aggregation_function": ["min", "max"]},                   [("aggregationFunction", "min"), ("aggregationFunction", "max")]),

        # None values are dropped
        ({"type": "X", "owner": None},                               [("type", "X")]),
        ({},                                                         []),

        # with_source_* require source but otherwise are not propagated
        ({"source": "S", "with_source_devices": True},               [("source", "S")]),
    ],
    ids=[
        "passthrough",
        "source",
        "name",
        "bulk_id-renamed",
        "kwarg-snake-to-camelCase",
        "kwarg-already-camelCase",
        "fragment→fragmentType",
        "reverse→revert+bool",
        "before→dateTo",
        "after→dateFrom",
        "date_to→dateTo",
        "date_from→dateFrom",
        "created_before→createdTo",
        "created_after→createdFrom",
        "created_to→createdTo",
        "created_from→createdFrom",
        "updated_before→lastUpdatedTo",
        "updated_after→lastUpdatedFrom",
        "last_updated_to→lastUpdatedTo",
        "last_updated_from→lastUpdatedFrom",
        "date_from-datetime-obj",
        "bool-false-encoded",
        "series-scalar",
        "series-list",
        "agg-fn-scalar",
        "agg-fn-list",
        "none-dropped",
        "empty",
        "with_source_devices-consumed",
    ],
)
def test_map_params(kwargs, expected):
    assert map_params(**kwargs) == expected


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"min_age": td(hours=1), "before":  "T"},                   "min_age"),
        ({"min_age": td(hours=1), "date_to": "T"},                   "min_age"),
        ({"max_age": td(hours=1), "after":   "T"},                   "max_age"),
        ({"max_age": td(hours=1), "date_from": "T"},                 "max_age"),
        ({"created_from": "T", "created_after":  "T"},               "created"),
        ({"created_to":   "T", "created_before": "T"},               "created"),
        ({"last_updated_from": "T", "updated_after":  "T"},          "updated"),
        ({"last_updated_to":   "T", "updated_before": "T"},          "updated"),
        ({"with_source_devices": True},                              "source"),
        ({"with_source_assets":  True},                              "source"),
    ],
    ids=[
        "min_age-vs-before",
        "min_age-vs-date_to",
        "max_age-vs-after",
        "max_age-vs-date_from",
        "created_from-vs-created_after",
        "created_to-vs-created_before",
        "last_updated_from-vs-updated_after",
        "last_updated_to-vs-updated_before",
        "with_source_devices-without-source",
        "with_source_assets-without-source",
    ],
)
def test_map_params_rejects(kwargs, match):
    with pytest.raises(ValueError, match=match):
        map_params(**kwargs)


@pytest.mark.parametrize("kwarg, expected_key", [
    ("min_age", "dateTo"),
    ("max_age", "dateFrom"),
])
def test_map_params_age_coercion(monkeypatch, kwarg, expected_key):
    """min_age/max_age are subtracted from `now()` and emitted as dateTo/dateFrom."""
    frozen_now = dt(2026, 1, 1, tzinfo=UTC)
    monkeypatch.setattr("pyc8y.model.model_base.now_datetime", lambda: frozen_now)
    result = map_params(**{kwarg: td(hours=1)})
    assert result == [(expected_key, "2025-12-31T23:00:00.000Z")]
