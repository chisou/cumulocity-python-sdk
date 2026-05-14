# Copyright (c) 2026 Christoph Souris

import random

from pyc8y.model.user import InventoryRole, Permission, ReadPermission, WritePermission
from tests.model.conftest import load_sample_file

SAMPLE_JSON = load_sample_file('inventoryrole.json')


def test_parsing():
    """Verify that parsing an InventoryRole from JSON works."""
    role = InventoryRole.from_json(SAMPLE_JSON)

    assert role.id == SAMPLE_JSON['id']
    assert role.name == SAMPLE_JSON['name']
    assert role.description == SAMPLE_JSON['description']

    permissions = {p.id: p for p in role.permissions}
    assert set(permissions.keys()) == {p['id'] for p in SAMPLE_JSON['permissions']}

    for p_json in SAMPLE_JSON['permissions']:
        pid = p_json['id']
        assert permissions[pid].type == p_json['type']
        assert permissions[pid].scope == p_json['scope']
        assert permissions[pid].level == p_json['permission']


def test_formatting():
    """Verify that to_json formatting works as expected."""
    permissions = [
        ReadPermission(scope=Permission.Scope.ANY),
        WritePermission(scope=Permission.Scope.MEASUREMENT, type='c8y_Custom'),
    ]
    role = InventoryRole(name='SomeRole', description='SomeDescription', permissions=permissions)

    # Permission is a dict; assign IDs via key access and write back
    perms = role.permissions
    for p in perms:
        p["id"] = random.randint(1, 999)
    role.permissions = perms

    full_json = role.json
    assert full_json['name'] == 'SomeRole'
    assert full_json['description'] == 'SomeDescription'

    json_permissions = {p['id']: p for p in full_json['permissions']}
    for p in role.permissions:
        jp = json_permissions[p.id]
        assert jp['type'] == p.type
        assert jp['scope'] == p.scope
        assert jp['permission'] == p.level


def test_formatting_diff():
    """Verify that _staged_json returns only staged changes."""
    role = InventoryRole.from_json(SAMPLE_JSON)

    role.name = "NewName"
    diff_json = role._staged_json

    assert diff_json['name'] == 'NewName'
    assert 'description' not in diff_json
    assert 'permissions' not in diff_json
