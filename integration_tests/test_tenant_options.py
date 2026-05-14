# Copyright (c) 2026 Christoph Souris

import pytest

from pyc8y.client import CumulocityClient
from pyc8y.model.tenant_option import TenantOption

from util.testing_util import create_random_name


async def test_crud(live_c8y: CumulocityClient):
    """Verify that create/read/update/delete works for tenant options using
    the object-oriented functions."""

    category = create_random_name()
    option = None
    try:
        # 1) create an option
        option = await TenantOption(live_c8y, category=category, key='my_key', value='test value').create()

        # 2) verify option values
        assert option.key == "my_key"
        assert option.value == "test value"

        # 3) verify reread from database
        assert (await live_c8y.tenant_options.get(option.category, option.key)).value == 'test value'
        assert (await live_c8y.tenant_options.get_all(limit=None, as_map=True))[category]['my_key'] == 'test value'
        assert await live_c8y.tenant_options.get_value(option.category, option.key) == 'test value'

        # 2) update the option
        option.value = 'new value'
        option = await option.update()
        assert option.value == 'new value'
        assert await live_c8y.tenant_options.get_value(option.category, option.key) == 'new value'

        # 3) delete the option
        await option.delete()
        with pytest.raises(KeyError):
            await live_c8y.tenant_options.get(option.category, option.key)
        option = None

    finally:
        if option:
            await option.delete()


async def test_crud_2(live_c8y: CumulocityClient):
    """Verify that create/read/update/delete works for tenant options using
    the procedural functions."""

    category = create_random_name()
    option = None
    try:
        # 1) create an option
        option = TenantOption(live_c8y, category=category, key='my_key', value='test value')
        await live_c8y.tenant_options.create(option)
        assert await live_c8y.tenant_options.get_value(option.category, option.key) == 'test value'

        # 2) update the option
        option.value = 'new value'
        await live_c8y.tenant_options.update(option)
        assert await live_c8y.tenant_options.get_value(option.category, option.key) == 'new value'

        # 3) delete the option
        await live_c8y.tenant_options.delete(option)
        with pytest.raises(KeyError):
            await live_c8y.tenant_options.get(option.category, option.key)
        option = None

    finally:
        if option:
            await live_c8y.tenant_options.delete(option)


async def test_get_all(live_c8y: CumulocityClient):
    """Verify that selecting tenant options works as expected."""
    all_options = await live_c8y.tenant_options.get_all(limit=None)

    categories = {x.category for x in all_options}
    by_category = {c: [x for x in all_options if x.category == c] for c in categories}
    for category, xs in by_category.items():
        options_mapped = await live_c8y.tenant_options.get_values(category)
        assert len(options_mapped) == len(by_category[category])
        # the API behave inconsistently, hence we remove the credentials. prefix if present
        assert {x.removeprefix("credentials.") for x in options_mapped.keys()} == {x.key for x in xs}


async def test_set_value_and_update_values_and_delete(live_c8y: CumulocityClient):
    """Verify that functions set_value, update_values and delete work as expected."""

    category = create_random_name()
    key = 'my_key'
    try:
        # 1) create an option
        await live_c8y.tenant_options.set_value(category=category, key=key, value='test value')

        # 2) update the option
        await live_c8y.tenant_options.update_values(category, {key: 'new value'})
        assert await live_c8y.tenant_options.get_value(category, key) == 'new value'

        # 3) delete the option
        await live_c8y.tenant_options.delete(category=category, key=key)
        with pytest.raises(KeyError):
            await live_c8y.tenant_options.get(category, key)

    finally:
        try:
            await live_c8y.tenant_options.delete(category=category, key=key)
        except KeyError:
            pass
