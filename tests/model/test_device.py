# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris

# pylint: disable=redefined-outer-name

import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyc8y.model.managed_object import Device
from pyc8y.types import MimeType
from tests.utils import isolate_last_call_arg


@pytest.fixture(scope="function")
def function_device() -> Device:
    """Provide a sample object for various tests."""
    return Device(name="name", type="type", owner="owner",
                  simple_string="string",
                  simple_int=123,
                  simple_float=123.4,
                  simple_true=True,
                  simple_false=False,
                  complex_1={"level0": "value"},
                  complex_2={"string": "value", "level0": {"level1": "value"}})


@pytest.fixture(scope="session")
def sample_json() -> dict:
    """Provide sample device JSON."""
    path = os.path.dirname(__file__) + "/device.json"
    with open(path, encoding="utf-8", mode="rt") as f:
        return json.load(f)


def test_formatting(function_device: Device):
    """Verify that JSON formatting works."""
    object_json = function_device.json

    assert object_json["name"] == function_device.name
    assert object_json["type"] == function_device.type
    assert object_json["owner"] == function_device.owner
    assert "c8y_IsDevice" in object_json

    assert object_json["simple_string"] == function_device["simple_string"]
    assert object_json["simple_int"] == function_device["simple_int"]
    assert object_json["simple_float"] == function_device["simple_float"]
    assert object_json["simple_true"] is True
    assert object_json["simple_false"] is False
    assert object_json["complex_1"]["level0"] == "value"
    assert object_json["complex_2"]["level0"]["level1"] == "value"

    expected_keys = {"name", "type", "owner", "c8y_IsDevice",
                     "simple_string", "simple_int", "simple_float", "simple_true", "simple_false",
                     "complex_1", "complex_2"}
    assert set(object_json.keys()) == expected_keys


def test_parsing(sample_json):
    """Verify that parsing a Device from JSON works."""

    d = Device.from_json(sample_json)

    # 2) assert parsed data
    assert d.id == sample_json["id"]
    assert d.type == sample_json["type"]
    assert d.name == sample_json["name"]
    assert d.creation_time == sample_json["creationTime"]
    assert d.is_device
    assert d.creation_datetime

    # 3) custom fragments
    assert d["c8y_SupportedOperations"] == sample_json["c8y_SupportedOperations"]
    test_json = sample_json["c8y_DataPoint"]["test"]
    assert d["c8y_DataPoint.test.string"] == test_json["string"]
    assert d["c8y_DataPoint.test.int"] == test_json["int"]
    assert d["c8y_DataPoint.test.float"] == test_json["float"]
    assert d["c8y_DataPoint.test.true"] == test_json["true"]
    assert d["c8y_DataPoint.test.false"] == test_json["false"]


async def test_create(function_device: Device, sample_json: dict):
    """Verify that the .create() function will result in the correct POST request."""

    c8y_mock = MagicMock()
    c8y_mock.post = AsyncMock(return_value=sample_json)
    function_device.c8y = c8y_mock
    await function_device.create()

    # -> accept header should be customized to managed object
    accept_arg = isolate_last_call_arg(c8y_mock.post, name="accept")
    assert accept_arg == MimeType.MANAGED_OBJECT

    # -> posted JSON should contain all the device's fields
    posted_json = isolate_last_call_arg(c8y_mock.post, name="json")
    expected_keys = {"name", "type", "owner", "c8y_IsDevice",
                     "simple_string", "simple_int", "simple_float", "simple_true", "simple_false",
                     "complex_1", "complex_2"}
    assert set(posted_json.keys()) == expected_keys


async def test_update(sample_json: dict):
    """Verify that the .update() function will result in the correct PUT request."""
    # build a device from JSON (so it has an ID and the source data is "committed")
    device = Device.from_json(sample_json)

    # standard updatable attributes
    device.name = "new_name"
    device.type = "new_type"
    device.owner = "new_owner"
    # simple fragments
    device["simple_fragment"] = "value"
    device["complex_fragment"] = {"level0": "value"}

    c8y_mock = MagicMock()
    c8y_mock.put = AsyncMock(return_value=sample_json)
    device.c8y = c8y_mock

    await device.update()

    assert isolate_last_call_arg(c8y_mock.put, name="accept") == MimeType.MANAGED_OBJECT

    # The updated JSON contains only changed fields
    posted_json = isolate_last_call_arg(c8y_mock.put, name="json")
    expected_keys = {"name", "type", "owner", "simple_fragment", "complex_fragment"}
    assert set(posted_json.keys()) == expected_keys
