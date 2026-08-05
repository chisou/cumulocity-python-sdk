# Copyright (c) 2026 Christoph Souris

import asyncio

import random
from typing import List

import pytest

from pyc8y.client import CumulocityClient
from pyc8y.model import Event, ManagedObject, Device
from pyc8y.model.matcher import jsonpath
from pyc8y.model.measurement import Measurement, Value
from pyc8y.model.model_base import ensure_ids

from util.testing_util import create_random_name


@pytest.fixture(name="mutable_object", scope="module")
async def fix_mutable_object(module_factory, request) -> ManagedObject:
    """Provide a single managed object ready to be changed during a test."""

    name = create_random_name()
    mo = ManagedObject(name=name, type=name, **{name: {'key': 'value'}})
    return await module_factory(mo)


async def test_update(mutable_object: ManagedObject):
    """Verify that updating managed objects works as expected."""

    mutable_object.name = mutable_object.name + '_altered'
    mutable_object.type = mutable_object.type + '_altered'
    mutable_object['new_attribute'] = 'value1'
    mutable_object['new_fragment'] = {'key': 'value2'}
    updated_object = await mutable_object.update(copy=True)

    assert updated_object.name == mutable_object.name
    assert updated_object.type == mutable_object.type
    assert updated_object["new_attribute"] == "value1"
    assert updated_object["new_fragment.key"] == "value2"


@pytest.fixture(name="similar_objects", scope="module")
async def fix_similar_objects(module_factory) -> List[ManagedObject]:
    """Provide a list of similar ManagedObjects (different name, everything
    else identical).  These are not to be changed."""

    n = 5
    basename = create_random_name()
    typename = basename

    objects = await asyncio.gather(*[
        module_factory(
            ManagedObject(name=f"{basename}_{i}", type=typename, **{f"{typename}_fragment": {}})
        )
        for i in range(1, n + 1)
    ])
    return objects


async def test_get_all(live_c8y: CumulocityClient):
    """Verify that the get_all query works as expected."""
    # (1) get all devices
    devices = await live_c8y.device_inventory.get_all(limit=100, )
    assert all("c8y_IsDevice" in d for d in devices)
    # (2) get all managed objects
    objects = await live_c8y.inventory.get_all(limit=100)
    # -> there should be both device and non-device objects
    device_objects = [o for o in objects if "c8y_IsDevice" in o]
    assert len(objects) > len(device_objects)
    # # (3) get all device groups
    groups = await live_c8y.group_inventory.get_all(limit=100)
    assert all("c8y_IsDeviceGroup" in g for g in groups)


@pytest.mark.parametrize('key, value_fun', [
    ('type', lambda mo: mo.type),
    ('name', lambda mo: mo.type + '*'),
    ('fragment', lambda mo: mo.type + '_fragment')
])
async def test_get_by_something(live_c8y: CumulocityClient, similar_objects: List[ManagedObject], key, value_fun):
    """Verify that managed objects can be selected by common type."""
    kwargs = {key: value_fun(similar_objects[0])}
    selected_mos = await live_c8y.inventory.get_all(**kwargs)
    assert set(ensure_ids(similar_objects)) == set(ensure_ids(selected_mos))
    assert await live_c8y.inventory.get_count(**kwargs) == len(similar_objects)


@pytest.mark.parametrize('query, value_fun', [
    ('type eq {}', lambda mo: mo.type),
    ('$filter=type eq {} $orderby=id', lambda mo: mo.type),
    ('$filter=name eq {}', lambda mo: mo.type + '*'),
    ('has({})', lambda mo: mo.type + '_fragment'),
])
async def test_get_by_query(live_c8y: CumulocityClient, similar_objects: List[ManagedObject], query: str, value_fun):
    """Verify that the selection by query works as expected."""
    query = query.replace('{}', value_fun(similar_objects[0]))
    selected_mos = await live_c8y.inventory.get_all(query=query)
    assert set(ensure_ids(similar_objects)) == set(ensure_ids(selected_mos))
    assert await live_c8y.inventory.get_count(query=query) == len(similar_objects)


async def test_filtering(live_c8y: CumulocityClient, safe_create):
    """Verify that client side filtering works as expected."""
    async def create_test_object(n):
        return await safe_create(ManagedObject(
            live_c8y,
            type='c8y_TestObject',
            name=f'c8y_TestObject_{n}',
            array=random.choices(range(10), k=5)
        ))

    objects = await asyncio.gather(
        *(create_test_object(i) for i in range(10))
    )

    # using filter parameter (JSONPath)
    filtered_1 = await live_c8y.inventory.get_all(
        limit=None,
        type='c8y_TestObject',
        fragment='array',
        include=jsonpath('$.array[?(@ == 0)]'))
    # using Python means
    filtered_2 = [
            mo async for mo in live_c8y.inventory.select(limit=None, type='c8y_TestObject', fragment='array')
            if 0 in mo.get("array", ())
    ]
    # -> no difference
    assert {x.name for x in filtered_1} == {x.name for x in filtered_2}

    await asyncio.gather(
        *(o.delete() for o in objects)
    )


async def test_get_single_by_query(live_c8y: CumulocityClient, module_factory):
    """Verify that the get_by function works as expected."""
    basename = create_random_name()
    typename = basename

    # create a couple of objects with two types
    objects = [
        await module_factory(ManagedObject(name=f'{basename}_1', type=f'{typename}_A')),
        await module_factory(ManagedObject(name=f'{basename}_2', type=f'{typename}_A')),
        await module_factory(ManagedObject(name=f'{basename}_3', type=f'{typename}_B')),
    ]

    # -> single matching query returns expected object
    assert (await live_c8y.inventory.get_by(type=f'{typename}_B')).id == objects[2].id

    # -> not matching query returns expected object
    with pytest.raises(ValueError) as error:
        await live_c8y.inventory.get_by(type=f'{typename}_C')
    assert "no matching object found" in str(error).lower()

    # -> not matching query returns expected object
    with pytest.raises(ValueError) as error:
        await live_c8y.inventory.get_by(type=f'{typename}_A')
    assert "ambiguous" in str(error).lower()


async def test_get_availability(live_c8y: CumulocityClient, session_device: Device):
    """Verify that the latest availability can be retrieved."""
    # set a required update interval
    session_device['c8y_RequiredAvailability'] = {'responseInterval': 10}
    await session_device.update()
    # create an event to trigger update
    await live_c8y.events.create(Event(type='c8y_TestEvent', time='now', source=session_device.id, text='Event!'))
    # verify availability information is defined
    # -> the information is updated asynchronously, hence this may be delayed
    availability = None
    for i in range(1, 6):
        await asyncio.sleep(pow(2, i))
        try:
            availability = await live_c8y.inventory.get_latest_availability(session_device.id)
            assert availability.last_message_time  # TODO: this is an API change, correct? (was last_message_date)
            break
        except KeyError:
            print("Availability not yet available (pun intended). Retrying ...")
    if not availability:
        pytest.skip("Availability not available (pun intended).")


async def test_reload(live_c8y):
    """Verify that the reload function works as expected.

    We only need to test this for the ManagedObject class, implicitly verifying
    the _reload function. The correct instrumentation of this abstract function
    by other inventory objects is verified through a unit test.
    """
    name = create_random_name()
    obj0 = await ManagedObject(live_c8y, name=f'Root-{name}', type=f'Root-{name}').create()

    # add a fragment
    await live_c8y.inventory.apply_to({'c8y_AdditionalFragment': {'key': 'value'}}, obj0.id)
    obj1 = await obj0.reload()
    # -> should be read from Cumulocity
    assert obj1.name == obj0.name
    assert obj1.creation_time == obj0.creation_time
    assert obj1.get("c8y_AdditionalFragment.key") == 'value'

    # remove a fragment
    await live_c8y.inventory.apply_to({'c8y_AdditionalFragment': None}, obj0.id)
    obj2 = await obj0.reload()
    # -> should be removed when reloaded
    assert "c8y_AdditionalFragment" not in obj2


@pytest.fixture(name='asset_hierarchy_root_id', scope='module')
async def fix_asset_hierarchy_root_id(module_factory):
    """Provide a (read-only) sample asset hierarchy for corresponding tests.

    This fixture creates a root object with a child of each kind (asset,
    device, addition). Each of the children references to another 'addition'
    child to create a multi-level hierarchy.

    It is automatically cleaned up after testing.
    """
    name = create_random_name()
    obj, addition, asset, device = await asyncio.gather(
        module_factory(ManagedObject(name=f'Root-{name}', type=f'Root-{name}')),
        module_factory(ManagedObject(name=f'Addition-{name}', type=f'Addition-{name}')),
        module_factory(ManagedObject(name=f'Asset-{name}', type=f'Asset-{name}')),
        module_factory(Device(name=f'Device-{name}', type=f'Device-{name}')),
    )

    await asyncio.gather(
        obj.add_child_addition(addition),
        obj.add_child_asset(asset),
        obj.add_child_device(device),
    )

    sub_addition =  await module_factory(ManagedObject(name=f'SubAddition-{name}', type=f'Addition-{name}'))
    await asyncio.gather(
        addition.add_child_addition(sub_addition),
        asset.add_child_addition(sub_addition),
        device.add_child_addition(sub_addition),
    )

    return obj.id


async def test_references(live_c8y: CumulocityClient, asset_hierarchy_root_id):
    """Verify that parent references are handles as expected.

    This test uses the "asset_hierarchy" fixture which defines a root
    with children of each kind.
    """
    root_id = asset_hierarchy_root_id

    # (1) ignore children and parents
    result = await live_c8y.inventory.get(root_id, with_children=False)
    assert not result.child_assets
    assert not result.child_devices
    assert not result.child_additions
    assert not result.parent_assets
    assert not result.parent_devices
    assert not result.parent_additions

    # (2) include children, with names
    result = await live_c8y.inventory.get(root_id, with_children=True, skip_children_names=False)
    # -> the root object references one of each
    assert len(result.child_assets) == 1
    assert len(result.child_devices) == 1
    assert len(result.child_additions) == 1
    # -> including their names
    assert result.child_assets[0].name
    assert result.child_devices[0].name
    assert result.child_additions[0].name
    # -> but no parents
    assert not result.parent_assets
    assert not result.parent_devices
    assert not result.parent_additions

    # (3) include children, no names
    result = await live_c8y.inventory.get(root_id, with_children=True, skip_children_names=True)
    # -> the root object references one of each
    assert len(result.child_assets) == 1
    assert len(result.child_devices) == 1
    assert len(result.child_additions) == 1
    # -> including their names
    assert not result.child_assets[0].name
    assert not result.child_devices[0].name
    assert not result.child_additions[0].name


@pytest.mark.parametrize('child_type', ['asset', 'device', 'addition'])
async def test_parent_references(live_c8y: CumulocityClient, asset_hierarchy_root_id, child_type):
    """Verify that parent references are handles as expected.

    This test uses the "asset_hierarchy" fixture which defines a root
    with children of each kind. Each kind has another "addition" child.
    """
    root = await live_c8y.inventory.get(asset_hierarchy_root_id, with_children=True)
    child = getattr(root, f"child_{child_type}s")[0]

    # read child with references
    result = await live_c8y.inventory.get(child.id,  with_children=True, with_parents=True)
    # parent (root) is linked by the child's type
    parents = getattr(result, f"parent_{child_type}s")
    assert len(parents) == 1
    assert parents[0].id == root.id
    assert parents[0].name == root.name
    # each child as an 'addition' child
    assert len(result.child_additions) == 1

    # using get_all
    result2 = await live_c8y.inventory.get_all(name=child.name, with_children=True, with_parents=True)
    assert len(result2) == 1
    parents2 = getattr(result2[0], f"parent_{child_type}s")
    assert parents[0].id == parents2[0].id
    assert parents[0].name == parents2[0].name


async def test_deletion(live_c8y: CumulocityClient, safe_create):
    """Verify that deletion works as expected.

    This test creates a managed object tree (root plus child asset, child device and child addition).
    Deleting the root object will not delete the children unless the 'cascade' option is used
    (using the delete_tree function).
    """
    name = create_random_name()
    obj = await safe_create(ManagedObject(name=f'Root-{name}', type=f'Root-{name}'))
    addition = await safe_create(ManagedObject(name=f'Addition-{name}', type=f'Addition-{name}'))
    asset = await safe_create(ManagedObject(name=f'Asset-{name}', type=f'Asset-{name}'))
    device = await safe_create(Device(name=f'Device-{name}', type=f'Device-{name}'))
    await asyncio.gather(
        obj.add_child_addition(addition),
        obj.add_child_asset(asset),
        obj.add_child_device(device),
    )

    await obj.reload()
    assert len(obj.child_additions) == 1
    assert obj.child_additions[0].id == addition.id
    assert len(obj.child_assets) == 1
    assert obj.child_assets[0].id == asset.id
    assert len(obj.child_devices) == 1
    assert obj.child_devices[0].id == device.id

    # delete the root managed object
    await obj.delete()
    # -> everything else is still around
    await asyncio.gather(
        addition.reload(),
        asset.reload(),
        device.reload(),
    )

    # assign to a new root
    obj = await safe_create(ManagedObject(name=f'Root-{name}', type=f'Root-{name}'))
    await asyncio.gather(
        obj.add_child_addition(addition),
        obj.add_child_asset(asset),
        obj.add_child_device(device),
    )
    # delete tree
    await obj.delete_tree()
    # -> everything else is gone as well
    with pytest.raises(KeyError):
        await addition.reload()
    with pytest.raises(KeyError):
        await asset.reload()
    with pytest.raises(KeyError):
        await device.reload()


async def test_device_deletion(live_c8y: CumulocityClient, safe_create):
    """Verify that device deletion works as expected.

    This test creates a device tree (root plus child asset, child device and child addition).
    Deleting the root device will not delete the children unless the 'cascade' option is used
    (using the delete_tree function).
    """
    name = create_random_name()
    async with asyncio.TaskGroup() as tg:
        t_obj = tg.create_task(safe_create(Device(name=f'Root-{name}', type=f'Root-{name}')))
        t_addition = tg.create_task(safe_create(ManagedObject(name=f'Addition-{name}', type=f'Addition-{name}')))
        t_asset = tg.create_task(safe_create(ManagedObject(name=f'Asset-{name}', type=f'Asset-{name}')))
        t_device = tg.create_task(safe_create(Device(name=f'Device-{name}', type=f'Device-{name}')))
    obj, addition, asset, device = t_obj.result(), t_addition.result(), t_asset.result(), t_device.result()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(obj.add_child_addition(addition))
        tg.create_task(obj.add_child_asset(asset))
        tg.create_task(obj.add_child_device(device))

    await obj.reload()
    assert len(obj.child_additions) == 1
    assert obj.child_additions[0].id == addition.id
    assert len(obj.child_assets) == 1
    assert obj.child_assets[0].id == asset.id
    assert len(obj.child_devices) == 1
    assert obj.child_devices[0].id == device.id

    # delete the root managed object
    await obj.delete()
    # -> everything else is still around
    async with asyncio.TaskGroup() as tg:
        tg.create_task(addition.reload())
        tg.create_task(asset.reload())
        tg.create_task(device.reload())

    # assign to a new root
    obj = await safe_create(Device(name=f'Root-{name}', type=f'Root-{name}'))
    async with asyncio.TaskGroup() as tg:
        tg.create_task(obj.add_child_addition(addition))
        tg.create_task(obj.add_child_asset(asset))
        tg.create_task(obj.add_child_device(device))
    # delete tree
    await obj.delete_tree()
    # -> everything else is gone as well
    with pytest.raises(KeyError):
        await addition.reload()
    with pytest.raises(KeyError):
        await asset.reload()
    with pytest.raises(KeyError):
        await device.reload()


@pytest.fixture(name="object_with_measurements", scope="function")
async def fix_object_with_measurements(live_c8y: CumulocityClient, mutable_object: ManagedObject) -> ManagedObject:
    """Provide a managed object with predefined measurements."""
    ms = [
        Measurement(
            live_c8y,
            type='c8y_TestMeasurementType',
            source=mutable_object.id,
            time='now',
            series=("c8y_Counter.N", i , "#"),
            c8y_Integers = {
                'V1': Value(i, ''),
                'V2' : Value(i*i, '')
            })
        for i in range(5)
    ]
    await live_c8y.measurements.create(*ms)
    return mutable_object


async def test_get_supported_measurements(live_c8y: CumulocityClient, object_with_measurements: ManagedObject):
    """Verify that the supported measurements can be retrieved."""
    result = await live_c8y.inventory.get_supported_measurements(object_with_measurements.id)
    assert set(result) == {'c8y_Counter', 'c8y_Integers'}


async def test_get_supported_measurements_2(live_c8y: CumulocityClient, object_with_measurements: ManagedObject):
    """Verify that the supported measurements can be retrieved."""
    result = await object_with_measurements.get_supported_measurements()
    assert set(result) == {'c8y_Counter', 'c8y_Integers'}


async def test_get_supported_series(live_c8y: CumulocityClient, object_with_measurements: ManagedObject):
    """Verify that the supported measurement series can be retrieved."""
    result = await live_c8y.inventory.get_supported_series(object_with_measurements.id)
    assert set(result) == {'c8y_Counter.N', 'c8y_Integers.V1', 'c8y_Integers.V2'}


async def test_get_supported_series_2(live_c8y: CumulocityClient, object_with_measurements: ManagedObject):
    """Verify that the supported measurement series can be retrieved."""
    result = await object_with_measurements.get_supported_series()
    assert set(result) == {'c8y_Counter.N', 'c8y_Integers.V1', 'c8y_Integers.V2'}
