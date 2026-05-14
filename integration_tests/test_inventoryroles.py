# Copyright (c) 2026 Christoph Souris

import pytest

from pyc8y.client import CumulocityClient
from pyc8y.model.user import User, InventoryRole, Permission, ReadPermission, WritePermission, AnyPermission

from util.testing_util import create_random_name


async def test_crud(live_c8y: CumulocityClient):
    """Verify that object-oriented create, update and delete works."""
    role = None
    try:
        permissions = [
            ReadPermission(scope=Permission.Scope.ANY),
            WritePermission(scope=Permission.Scope.MEASUREMENT, type='c8y_Custom'),
            AnyPermission(scope=Permission.Scope.ALARM, type='*'),
        ]
        role = await InventoryRole(
            live_c8y, name=create_random_name(), description='SomeDescription', permissions=permissions
        ).create()

        assert role.id
        assert all(p.id for p in role.permissions)

        # update: change description and remove first permission
        role.description = 'new description'
        perms = role.permissions[1:]
        role.permissions = perms
        updated = await role.update()

        assert updated.id == role.id
        assert updated.description == 'new description'
        assert {p.id for p in updated.permissions} == {p.id for p in role.permissions}

        # delete
        await role.delete()
        with pytest.raises(KeyError):
            await live_c8y.inventory_roles.get(role.id)
        role = None

    finally:
        if role:
            await role.delete()


async def test_crud_2(live_c8y: CumulocityClient):
    """Verify that API-based create, update and delete works."""
    role = None
    try:
        permissions = [
            ReadPermission(scope=Permission.Scope.ANY),
            WritePermission(scope=Permission.Scope.MEASUREMENT, type='c8y_Custom'),
            AnyPermission(scope=Permission.Scope.ALARM, type='*'),
        ]
        role = InventoryRole(name=create_random_name(), description='SomeDescription', permissions=permissions)
        await live_c8y.inventory_roles.create(role)

        # find just-created role
        all_roles = await live_c8y.inventory_roles.get_all(limit=None)
        created = next(r for r in all_roles if r.name == role.name)

        # update via API
        created.description = 'new description'
        await live_c8y.inventory_roles.update(created)

        updated = await live_c8y.inventory_roles.get(created.id)
        assert updated.description == 'new description'

        # delete via API
        await live_c8y.inventory_roles.delete(created.id)
        with pytest.raises(KeyError):
            await live_c8y.inventory_roles.get(created.id)
        role = None

    finally:
        if role:
            try:
                all_roles = await live_c8y.inventory_roles.get_all(limit=None)
                leftover = next((r for r in all_roles if r.name == role.name), None)
                if leftover:
                    await live_c8y.inventory_roles.delete(leftover.id)
            except Exception:
                pass


async def test_select(live_c8y: CumulocityClient):
    """Verify that selection and filtering work as expected."""
    all_roles = await live_c8y.inventory_roles.get_all(limit=None)
    assert all_roles

    # client-side include filter
    with_desc = await live_c8y.inventory_roles.get_all(limit=None, include='description != null')
    without_desc = [r for r in all_roles if not r.description]
    assert {r.id for r in with_desc} == {r.id for r in all_roles} - {r.id for r in without_desc}


async def test_assignments(live_c8y: CumulocityClient, session_device, module_factory):
    """Verify that inventory roles can be assigned, retrieved and unassigned."""
    email = 'user_' + create_random_name() + '@test.com'
    role1 = await module_factory(InventoryRole(name='role_' + create_random_name(), permissions=[
        ReadPermission(scope=Permission.Scope.ALARM),
        WritePermission(scope=Permission.Scope.AUDIT),
    ]))
    role2 = await module_factory(InventoryRole(name='role_' + create_random_name(), permissions=[
        ReadPermission(scope=Permission.Scope.ANY),
        WritePermission(scope=Permission.Scope.MEASUREMENT),
    ]))
    user = await module_factory(User(username=email, email=email))

    # assign inventory roles
    await user.assign_inventory_roles(session_device.id, role1, role2)

    # verify assignments
    assignments = await user.retrieve_inventory_role_assignments()
    assert len(assignments) == 1
    assert {role1.name, role2.name} == {r.name for r in assignments[0].roles}

    # unassign
    await user.unassign_inventory_roles(assignments[0].id)
    assert not await user.retrieve_inventory_role_assignments()
