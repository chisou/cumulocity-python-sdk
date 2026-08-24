# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyc8y.model.alarm import Alarms
from pyc8y.model.audit import AuditRecords
from pyc8y.model.event import Events
from pyc8y.model.inventory import Inventory, DeviceInventory, DeviceGroupInventory
from pyc8y.model.operation import Operations


@pytest.mark.parametrize("resource_class", [
    Events,
    Alarms,
    Operations,
    AuditRecords,
    Inventory,
    DeviceInventory,
    DeviceGroupInventory,
])
async def test_client_side_filtering(resource_class):
    """Verify that client side filtering works as expected.

    This test prepares a mocked CumulocityClient and runs the get_all function
    against it. The REST GET is mocked as well as corresponding matcher
    results. The test verifies that the matcher is invoked and applied.
    """
    # create mock CumulocityClient instance
    c8y = MagicMock()
    c8y.tenant_id = "t123"
    resource = resource_class(c8y=c8y)
    collection_name = resource._meta.collection_name

    # prepare mock data and corresponding matchers
    # the get function is invoked until there are no results (empty list), the results
    # are stored in an array by collection name
    get_data = [
        {collection_name: x, "statistics": {"totalPages": 1}} for x in
        [
            [{"id": 1, "source": {"id": 1}}, {"id": 2, "source": {"id": 2}}, {"id": 3, "source": {"id": 3}}],
            [],
        ]
    ]
    include_results = [True, False, True]
    exclude_results = [True, False]

    c8y.get = AsyncMock(side_effect=get_data)
    include_matcher = MagicMock(safe_matches=MagicMock(side_effect=include_results))
    exclude_matcher = MagicMock(safe_matches=MagicMock(side_effect=exclude_results))

    # run get_all/select
    result = await resource.get_all(include=include_matcher, exclude=exclude_matcher)

    # -> result should only contain filtered documents
    #    1,2,3 -> 1,3 -> 3
    assert ["3"] == [str(x.id) for x in result]
    # -> include matcher should have been called for each document
    assert include_matcher.safe_matches.call_count == len(include_results)
    # -> exclude matcher should have been called for each included
    assert exclude_matcher.safe_matches.call_count == len(exclude_results)
