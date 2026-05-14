# Copyright (c) 2026 Christoph Souris

import pytest

from pyc8y.model.notification2 import Subscription

from tests.model.conftest import load_sample_file


@pytest.mark.parametrize('sample_json', load_sample_file("subscriptions.json")["subscriptions"])
def test_parsing(sample_json):
    """Verify that parsing a Subscription from JSON works as expected."""
    sub = Subscription.from_json(sample_json)

    assert sub.name == sample_json['subscription']
    assert sub.context == sample_json['context']
    assert sub.source_id == sample_json['source']['id']

    if 'nonPersistent' in sample_json:
        assert sub.non_persistent == sample_json['nonPersistent']
    if 'fragmentsToCopy' in sample_json:
        assert sub.fragments == sample_json['fragmentsToCopy']
    if 'subscriptionFilter' in sample_json:
        sf = sample_json['subscriptionFilter']
        if 'apis' in sf:
            assert sub.api_filter == sf['apis']
        if 'typeFilter' in sf:
            assert sub.type_filter == sf['typeFilter']


def test_formatting():
    """Verify that to_json formatting works as expected."""
    sub = Subscription(name='name', source_id='source_id', context=Subscription.Context.TENANT)

    sub_json = sub.json
    assert sub_json['subscription'] == 'name'
    assert sub_json['context'] == 'tenant'
    assert sub_json['source'] == {'id': 'source_id'}
    assert len(sub_json) == 3

    sub.fragments = ['f1', 'f2']
    sub.type_filter = 'type_filter'
    sub_json = sub.json
    assert sub_json['fragmentsToCopy'] == sub.fragments
    assert sub_json['subscriptionFilter']['typeFilter'] == sub.type_filter
    assert len(sub_json) == 5

    sub.api_filter = ['a1', 'a2']
    sub.non_persistent = True
    sub_json = sub.json
    assert sub_json['subscriptionFilter']['typeFilter'] == sub.type_filter
    assert sub_json['subscriptionFilter']['apis'] == sub.api_filter
    assert sub_json['nonPersistent'] is True
    assert len(sub_json) == 6


def test_context_constants():
    """Verify Subscription.Context constants."""
    assert Subscription.Context.MANAGED_OBJECT == 'mo'
    assert Subscription.Context.TENANT == 'tenant'


def test_api_filter_constants():
    """Verify Subscription.ApiFilter constants."""
    assert Subscription.ApiFilter.ALARMS == 'alarms'
    assert Subscription.ApiFilter.MEASUREMENTS == 'measurements'
    assert Subscription.ApiFilter.ANY == '*'
