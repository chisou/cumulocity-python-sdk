# Copyright (c) 2026 Christoph Souris

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyc8y.model.notification2 import Subscription, Subscriptions

from tests.model.conftest import load_sample_file


@pytest.fixture
def subscriptions():
    return load_sample_file("subscriptions.json")


async def test_get_all(subscriptions):
    """Verify that Subscriptions.get_all returns parsed Subscription objects."""
    c8y = MagicMock()
    c8y.get = AsyncMock(side_effect=[subscriptions, {'subscriptions': []}])

    results = await Subscriptions(c8y).get_all()

    assert len(results) == 4
    assert all(isinstance(r, Subscription) for r in results)


async def test_select_params():
    """Verify that select parameters are forwarded to the HTTP call."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'subscriptions': [], 'statistics': {'totalPages': 1}})

    api = Subscriptions(c8y)
    _ = [r async for r in api.select(
        context='mo', source='S', subscription='SU', type_filter='F', page_number=1,
    )]

    params = dict(c8y.get.call_args.kwargs["params"])
    assert params['context'] == 'mo'
    assert params['source'] == 'S'
    assert params['subscription'] == 'SU'
    assert params['typeFilter'] == 'F'


async def test_select_expression_overrides_filters():
    """Verify that expression overrides other filters."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'subscriptions': [], 'statistics': {'totalPages': 1}})

    api = Subscriptions(c8y)
    _ = [r async for r in api.select(expression='context=mo', context='ignored', page_number=1)]

    call_url = c8y.get.call_args.args[0]
    assert 'context=mo' in call_url
    # no params tuple when expression is used
    assert "params" not in c8y.get.call_args.kwargs


async def test_get_count():
    """Verify that get_count returns an integer."""
    c8y = MagicMock()
    c8y.get = AsyncMock(return_value={'subscriptions': [], 'statistics': {'totalPages': 3}})

    api = Subscriptions(c8y)
    count = await api.get_count(context='mo', source='S')

    assert count == 3
    params = dict(c8y.get.call_args.kwargs["params"])
    assert params['context'] == 'mo'
    assert params['source'] == 'S'
