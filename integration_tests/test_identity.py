# Copyright (c) 2025 Cumulocity GmbH

import pytest

from pyc8y.client import CumulocityClient
from pyc8y.model.identity import ExternalId

from util.testing_util import create_random_name


async def test_CRUD(live_c8y: CumulocityClient, session_device):
    """Verify that basic creation/removal and lookup of ID works as expected."""

    id_ref1 = create_random_name() + '-12345'
    id_ref2 = create_random_name() + '-12345'
    id_ref3 = create_random_name() + '-12345'
    id_type = 'external_id_type'

    external_id1 = await (ExternalId(
        live_c8y,
        external_id=id_ref1,
        external_type='external_id_type',
        managed_object_id=session_device.id,
    )).create()
    external_id2 = ExternalId(
        live_c8y,
        external_id=id_ref2,
        external_type='external_id_type',
        managed_object_id=session_device.id,
    )
    # create bulk
    await live_c8y.identity.create(external_id2)
    # create directly
    await live_c8y.identity.create(external_id=id_ref3, external_type=id_type, managed_object_id=session_device.id)

    try:
        # retrieve all linked external id
        ids = {i.external_id for i in await live_c8y.identity.get_all(session_device.id)}
        assert ids == {id_ref1, id_ref2, id_ref3}

        # retrieve the referenced object
        obj = await external_id1.get_object()
        # -> it is identical to the sample device
        assert obj.id == session_device.id

        # retrieve the object ID via API
        # -> identical to sample device ID
        assert await live_c8y.identity.get_id(id_ref1, id_type) == session_device.id

        # retrieve object via external id
        # -> identical to sample device ID
        assert (await live_c8y.identity.get_object(id_ref2, id_type)).id == session_device.id

    finally:
        # delete on object
        await external_id1.delete()
        # delete bulk
        await live_c8y.identity.delete(ExternalId(external_id=id_ref2, external_type=id_type))
        # delete directly
        await live_c8y.identity.delete(external_id=id_ref3, external_type=id_type)

    for id_ref in (id_ref1, id_ref2, id_ref3):
        with pytest.raises(KeyError):
            await live_c8y.identity.get(id_ref, id_type)
