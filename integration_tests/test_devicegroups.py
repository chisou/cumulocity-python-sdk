# Copyright (c) 2026 Christoph Souris

from __future__ import annotations

import asyncio

import pytest

from pyc8y.client import CumulocityClient
from pyc8y.model import DeviceGroup

from util.testing_util import create_random_name


async def test_CRUD(live_c8y: CumulocityClient, safe_create):
    """Verify that object-oriented create, update, and delete works as expected."""

    name = create_random_name()

    root, child1, child2 = asyncio.gather(
        await safe_create(DeviceGroup(live_c8y, root=True, name=f"Root-{name}", custom_fragment={"test": True})),
        await safe_create(DeviceGroup(live_c8y, name=f"Child1-{name}", custom_fragment={"test": True})),
        await safe_create(DeviceGroup(live_c8y, name=f"Child2-{name}", custom_fragment={"test": True})),
    )

    # assign children using batch method
    await live_c8y.group_inventory.assign_children(root.id, child1.id, child2.id, workers=2)

    # select all root groups — our root should be in there
    assert f"Root-{name}" in [x.name for x in await live_c8y.group_inventory.get_all(page_size=100, workers=5)]

    # select by parent — both children should appear
    child_names = [x.name for x in await live_c8y.group_inventory.get_all(parent=root.id)]
    assert len(child_names) == 2
    assert all(x.startswith("Child") for x in child_names)
    assert all(x.endswith(name) for x in child_names)

    # update child2
    child2["another_fragment"] = {"data": 12345}
    child2 = await child2.update()
    assert (await live_c8y.group_inventory.get(child2.id)).another_fragment.data == 12345

    # unassign child groups
    await root.unassign_child_group(child1.id)
    await root.unassign_child_group(child2)
    assert not await live_c8y.group_inventory.get_all(parent=root.id)

    # re-assign for the remainder of the test
    await live_c8y.group_inventory.assign_children(root.id, child1.id, child2.id)

    # delete child2
    await child2.delete()
    with pytest.raises(KeyError):
        await live_c8y.group_inventory.get(child2.id)

    # delete root cascading via object method
    await root.delete_tree()
    with pytest.raises(KeyError):
        await live_c8y.group_inventory.get(child1.id)
    with pytest.raises(KeyError):
        await live_c8y.group_inventory.get(root.id)


async def test_CRUD2(live_c8y: CumulocityClient, safe_create):
    """Verify that create, update, and delete via the API works as expected."""

    name = create_random_name()

    root = await safe_create(DeviceGroup(live_c8y, root=True, name=f"Root-{name}", custom_fragment={"test": True}))
    child1 = await safe_create(DeviceGroup(live_c8y, name=f"Child1-{name}", custom_fragment={"test": True}))
    child2 = await safe_create(DeviceGroup(live_c8y, name=f"Child2-{name}", custom_fragment={"test": True}))

    # 1) assign children
    await live_c8y.group_inventory.assign_children(root.id, child1.id, child2.id)
    child_names = [x.name for x in await live_c8y.group_inventory.get_all(parent=root.id, type=DeviceGroup.CHILD_TYPE)]
    assert len(child_names) == 2
    assert all(x.startswith("Child") for x in child_names)
    assert all(x.endswith(name) for x in child_names)

    # 2) unassign child1
    await live_c8y.group_inventory.unassign_children(root.id, child1.id)
    child_names = [x.name for x in await live_c8y.group_inventory.get_all(parent=root.id)]
    assert child_names == [child2.name]

    # 3) re-assign child1
    await live_c8y.group_inventory.assign_children(root.id, child1.id)
    assert len(await live_c8y.group_inventory.get_all(parent=root.id)) == 2

    # 4) delete entire tree
    await live_c8y.group_inventory.delete_trees(root.id)
    with pytest.raises(KeyError):
        await live_c8y.group_inventory.get(root.id)


async def test_trees(live_c8y: CumulocityClient, safe_create):
    """Verify that creation and deletion of device group trees works as expected."""

    name = create_random_name()
    root = await safe_create(DeviceGroup(live_c8y, root=True, name=f"Root-{name}"))
    child1 = await root.create_child(name=f"Child1-{name}")
    child2 = await root.create_child(name=f"Child2-{name}")
    child11 = await child1.create_child(name=f"Child11-{name}")
    child12 = await child1.create_child(name=f"Child12-{name}")
    child21 = await child2.create_child(name=f"Child21-{name}")

    assert {child1.id, child2.id} == {x.id for x in await live_c8y.group_inventory.get_all(parent=root.id)}
    assert {child11.id, child12.id} == {x.id for x in await live_c8y.group_inventory.get_all(parent=child1.id)}

    # remove child1 subtree — child11 and child12 should be gone
    await live_c8y.group_inventory.delete_trees(child1.id)
    assert not await live_c8y.group_inventory.get_all(parent=child1.id)

    # remove root cascading — child21 should be gone too
    await root.delete_tree()
    with pytest.raises(KeyError):
        await live_c8y.group_inventory.get(child21.id)
