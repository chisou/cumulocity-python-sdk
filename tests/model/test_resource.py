# Copyright (c) 2025 Cumulocity GmbH

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from pyc8y.model.model_base import CumulocityResource, map_params


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
        ({"revert": True},                                           [("dateFrom", "1970-01-01T00:00:00.000Z"), ("revert", "true")]),
        ({"revert": True, "date_from": "2020-01-01T00:00:00+00:00"}, [("dateFrom", "2020-01-01T00:00:00.000Z"), ("revert", "true")]),
        ({"revert": True, "before": "2020-01-01T00:00:00+00:00"},    [("dateTo", "2020-01-01T00:00:00.000Z"), ("revert", "true")]),

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
        ({"revert": False},                                          [("dateFrom", "1970-01-01T00:00:00.000Z"), ("revert", "false")]),

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
        "fragment_fragmentType",
        "revert_solo",
        "revert_date_from",
        "revert_before",
        "before_dateTo",
        "after_dateFrom",
        "date_to_dateTo",
        "date_from_dateFrom",
        "created_before_createdTo",
        "created_after_createdFrom",
        "created_to_createdTo",
        "created_from_createdFrom",
        "updated_before_lastUpdatedTo",
        "updated_after_lastUpdatedFrom",
        "last_updated_to_lastUpdatedTo",
        "last_updated_from_lastUpdatedFrom",
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


# -----------------------------------------------------------------------------
# Sliding-window worker behavior in _stream_pages / _iterate
# -----------------------------------------------------------------------------


async def test_stream_pages_yields_in_order_with_workers():
    """Pages are yielded in launch order even when later pages finish first."""
    res = CumulocityResource(Mock())

    async def fetch(page, **_):
        # earlier pages take longer _ later pages would finish first if order
        # weren't enforced. We expect them in launch order anyway.
        await asyncio.sleep((10 - page) * 0.005 if page <= 5 else 0)
        return [{"page": page}] if page <= 5 else []

    pages = []
    async for p in res._stream_pages(fetch, start_page=1, workers=3, expression=None, params=None):
        pages.append(p)

    # 5 non-empty + 1 sentinel empty
    assert [p[0]["page"] for p in pages if p] == [1, 2, 3, 4, 5]
    assert pages[-1] == []


async def test_stream_pages_keeps_workers_busy():
    """When a page completes, a new fetch is launched immediately — no batch stalls."""
    res = CumulocityResource(Mock())
    concurrency_observed = []
    in_flight = 0
    lock = asyncio.Lock()

    async def fetch(page, **_):
        nonlocal in_flight
        async with lock:
            in_flight += 1
            concurrency_observed.append(in_flight)
        try:
            await asyncio.sleep(0.005)
            return [{"page": page}] if page <= 6 else []
        finally:
            async with lock:
                in_flight -= 1

    pages = []
    async for p in res._stream_pages(fetch, start_page=1, workers=3, expression=None, params=None):
        pages.append(p)

    # at some point we should have seen `workers` concurrent fetches
    assert max(concurrency_observed) == 3


async def test_stream_pages_workers_one_is_sequential():
    """workers=1 falls back to plain sequential fetch."""
    res = CumulocityResource(Mock())
    seen = []

    async def fetch(page, **_):
        seen.append(page)
        return [{"page": page}] if page <= 3 else []

    async for _ in res._stream_pages(fetch, start_page=1, workers=1, expression=None, params=None):
        pass
    assert seen == [1, 2, 3, 4]


async def test_stream_pages_cancels_overshoot_on_empty():
    """Speculative fetches launched past the last full page are cancelled cleanly."""
    res = CumulocityResource(Mock())
    cancelled = []

    async def fetch(page, **_):
        try:
            await asyncio.sleep(0.005 * page)  # later pages take longer
            return [{"page": page}] if page <= 2 else []
        except asyncio.CancelledError:
            cancelled.append(page)
            raise

    async for _ in res._stream_pages(fetch, start_page=1, workers=4, expression=None, params=None):
        pass

    # we asked for 4 in-flight; pages 1,2 returned data, page 3 was empty (sentinel),
    # page 4 was launched before we saw the empty _ cancelled on exit
    assert 4 in cancelled
