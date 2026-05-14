# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris

# pylint: disable=redefined-outer-name

from __future__ import annotations

import json
import os

import pytest

from pyc8y.model.user import UserGroup


@pytest.fixture(scope='function')
def sample_role() -> UserGroup:
    """Provide a sample global role, read from JSON file."""
    path = os.path.dirname(__file__) + '/global_role.json'
    with open(path, encoding='utf-8', mode='rt') as f:
        role_json = json.load(f)

    return UserGroup.from_json(role_json)


def test_parsing():
    """Verify that parsing a UserGroup (Global Role) from JSON works."""
    path = os.path.dirname(__file__) + '/global_role.json'
    with open(path, encoding='utf-8', mode='rt') as f:
        role_json = json.load(f)
    role = UserGroup.from_json(role_json)

    assert role.id == role_json['id']
    assert role.name == role_json['name']
    assert role.description == role_json['description']

    expected_roles = {x['role']['id'] for x in role_json['roles']['references']}
    assert role.role_ids == expected_roles


def test_formatting():
    """Verify that rendering a global role as JSON works as expected."""
    role = UserGroup(name='My Role', description='A description')
    role_json = role.json
    assert 'id' not in role_json
    # we only expect
    expected_keys = {'name', 'description'}
    assert set(role_json.keys()) == expected_keys
