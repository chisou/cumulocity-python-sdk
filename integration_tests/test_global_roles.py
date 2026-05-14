# Copyright (c) 2026 Christoph Souris

import random

import pytest

from pyc8y.client import CumulocityClient
from pyc8y.model.user import User, UserGroup

from util.testing_util import create_random_name


async def test_crud(live_c8y: CumulocityClient):
    """Verify that basic CRUD functionality works."""
    rolename = create_random_name()

    role = UserGroup(c8y=live_c8y, name=rolename, description=f"{rolename} description")
    created_role = await role.create()
    try:
        assert created_role.id
        assert created_role.name == rolename
        assert created_role.description and rolename in created_role.description

        created_role.name = f"{rolename}_2"
        created_role.description = f"Updated {created_role.description}"
        updated_role = await created_role.update()

        assert updated_role.name == created_role.name
        assert updated_role.description == created_role.description
    finally:
        await created_role.delete()

    with pytest.raises(KeyError):
        await live_c8y.user_groups.get(created_role.id)


async def test_select(live_c8y: CumulocityClient, safe_create):
    """Verify that selection works as expected."""
    all_roles = await live_c8y.user_groups.get_all(page_size=100)

    username = create_random_name()
    email = f"{username}@c8y.com"
    user = await safe_create(User(live_c8y, username=username, email=email, enabled=True))
    selected_roles = random.sample(all_roles, k=5)
    for role in selected_roles:
        await user.assign_global_role(role.id)

    # verify assigned roles are a subset of what we assigned
    selected_ids = {r.id for r in selected_roles}
    for role in await live_c8y.user_groups.get_all(username=username, page_size=100):
        assert role.id in selected_ids

    # client-side filter on all roles
    filtered_1 = await live_c8y.user_groups.get_all(include="name contains Global")
    filtered_2 = [x for x in all_roles if "Global" in x.name]
    assert {x.name for x in filtered_1} == {x.name for x in filtered_2}

    # filter combined with username
    assigned = await live_c8y.user_groups.get_all(username=username)
    filtered_1 = await live_c8y.user_groups.get_all(username=username, include="name contains a")
    filtered_2 = [x for x in assigned if "a" in x.name]
    assert {x.name for x in filtered_1} == {x.name for x in filtered_2}

    await user.delete()


async def test_updating_users(live_c8y: CumulocityClient, safe_create):
    """Verify that users can be added/removed to/from a global role."""
    rolename = create_random_name()
    role = await safe_create(UserGroup(c8y=live_c8y, name=rolename, description=f"{rolename} description"))

    current_username = live_c8y.username

    groups = await live_c8y.user_groups.get_all(username=current_username)
    assert role.id not in {g.id for g in groups}

    await role.assign_users(current_username)
    groups = await live_c8y.user_groups.get_all(username=current_username)
    assert role.id in {g.id for g in groups}

    await role.unassign_users(current_username)
    groups = await live_c8y.user_groups.get_all(username=current_username)
    assert role.id not in {g.id for g in groups}


async def test_updating_permissions(live_c8y: CumulocityClient, module_factory):
    """Verify that permissions can be added/removed to/from a global role."""
    rolename = create_random_name()
    role = await module_factory(UserGroup(c8y=live_c8y, name=rolename, description=f"{rolename} description"))

    assert not role.role_ids
    new_permissions = {"ROLE_EVENT_READ", "ROLE_ALARM_READ"}

    await role.assign_roles(*new_permissions)
    assert (await live_c8y.user_groups.get(role.id)).role_ids == new_permissions

    removed = new_permissions.pop()
    await role.unassign_roles(removed)
    assert (await live_c8y.user_groups.get(role.id)).role_ids == new_permissions
