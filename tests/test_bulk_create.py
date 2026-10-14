# Copyright (c) 2026 Christoph Souris

# pylint: disable=protected-access

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pyc8y.model.measurement import Measurement, Measurements
from pyc8y.rest import BatchError, BatchContext
from pyc8y.types import MimeType


def _measurements(count: int) -> list[Measurement]:
    return [Measurement(type="t", source="1", time=f"2026-01-01T00:00:{i:02d}Z") for i in range(count)]


def _resource(fail_on_call: int | None = None) -> tuple[Measurements, list[dict]]:
    calls: list[dict] = []

    async def post(path, **kwargs):
        calls.append(kwargs)
        if len(calls) == fail_on_call:
            raise ValueError("500")
        return {"measurements": [{"id": f"{len(calls)}-{i}"} for i, _ in enumerate(kwargs["json"]["measurements"])]}

    c8y = MagicMock()
    c8y.post = post
    return Measurements(c8y), calls


async def test_create_bulk_returns_created_in_order():
    resource, calls = _resource()
    result = await resource.create_bulk(*_measurements(5), batch_size=2, workers=2)
    assert [m.id for m in result] == ["1-0", "1-1", "2-0", "2-1", "3-0"]
    assert calls[0]["content_type"] == MimeType.MEASUREMENT_COLLECTION
    assert calls[0]["accept"] == MimeType.MEASUREMENT_COLLECTION


async def test_create_with_batch_size_is_fire_and_forget():
    resource, calls = _resource()
    assert await resource.create(*_measurements(3), batch_size=2) is None
    assert len(calls) == 2
    assert calls[0]["content_type"] == MimeType.MEASUREMENT_COLLECTION
    assert calls[0]["accept"] is None


async def test_batch_error_carries_failed_objects():
    resource, _ = _resource(fail_on_call=2)
    measurements = _measurements(5)
    with pytest.raises(BatchError) as exc_info:
        await resource.create_bulk(*measurements, batch_size=2, workers=2)
    error = exc_info.value
    assert len(error.errors) == len(error.contexts) == 1
    assert isinstance(error.contexts[0], BatchContext)
    assert list(error.contexts[0].item) == measurements[2:4]
