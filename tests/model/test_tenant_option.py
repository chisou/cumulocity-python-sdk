# Copyright (c) 2026 Christoph Souris

import pytest
from unittest.mock import AsyncMock, MagicMock

from pyc8y.model.tenant_option import TenantOption, TenantOptions

from tests.model.conftest import load_sample_file

SAMPLES_JSON = load_sample_file("tenant_option.json")

@pytest.mark.parametrize("sample_json", SAMPLES_JSON)
def test_parsing(sample_json):
    """Verify that parsing a TenantOption from JSON works."""
    opt = TenantOption.from_json(sample_json)

    assert opt.category == sample_json['category']
    assert opt._key == sample_json['key']
    if not opt.is_encrypted:
        assert opt.key == sample_json['key']
    else:
        assert "credentials." + opt.key == sample_json['key']
    assert opt.value == sample_json['value']


@pytest.mark.parametrize("encrypted", [True, False])
def test_formatting(encrypted):
    """Verify that to_json formatting works as expected."""
    category = "some_category"
    key = "some_key"
    value = "some_value"
    opt = TenantOption(category=category, key=key, value=value, encrypted=encrypted)
    opt_json = opt.json

    assert opt_json['category'] == category
    assert opt_json['value'] == value
    if encrypted:
        assert opt_json['key'] == "credentials." + opt.key
    else:
        assert opt_json['key'] == opt.key


@pytest.mark.parametrize("sample_json", SAMPLES_JSON)
async def test_get(sample_json):
    """Verify that the get function works as expected."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value=sample_json)

    api = TenantOptions(c8y)
    opt = await api.get("category", "key")

    assert isinstance(opt, TenantOption)
    assert opt.category == sample_json['category']
    if sample_json['key'].startswith("credentials."):
        assert "credentials." + opt.key == sample_json['key']
    else:
        assert opt.key == sample_json['key']
    assert opt._key == sample_json['key']
    assert opt.value == sample_json['value']
    c8y.get.assert_called_once_with(f"tenant/options/category/key")


@pytest.mark.parametrize("sample_json", SAMPLES_JSON)
async def test_get_value(sample_json):
    """Verify that the get_value function works as expected."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value=sample_json)

    assert sample_json['value'] == await TenantOptions(c8y).get_value("category", "key")


async def test_get_all():
    """Verify that the get_all (and select) function works as expected."""
    c8y = MagicMock()
    c8y.get = AsyncMock(side_effect=[{'options': SAMPLES_JSON, 'statistics': {}}, {'options': []}])

    results = await TenantOptions(c8y).get_all()

    assert len(results) == len(SAMPLES_JSON)
    for r in results:
        assert isinstance(r, TenantOption)


async def test_get_all_as_map():
    """Verify that get_all can return the options as map.

    The "credentials." prefix is assumed to be automatically removed from
    options if they are encrypted.
    """
    c8y = MagicMock()
    c8y.get = AsyncMock(side_effect=[{'options': SAMPLES_JSON, 'statistics': {}}, {'options': []}])

    results = await TenantOptions(c8y).get_all(as_map=True)

    for o in SAMPLES_JSON:  # find matching options
        expected_category = o['category']
        expected_key = o['key'].removeprefix("credentials.")
        expected_value = o['value']
        assert results[expected_category][expected_key] == expected_value


async def test_get_values():
    """Verify that the get_values function works as expected.

    A single get request is expected which returns all key/value pairs of
    a certain category.

    """
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'key1': 'value1', 'key2': 'value2'})

    results = await TenantOptions(c8y).get_values('category')

    assert c8y.get.call_count == 1
    c8y.get.assert_called_once_with('tenant/options/category')
    assert len(results) == 2
    assert results['key1'] == 'value1'
    assert results['key2'] == 'value2'
