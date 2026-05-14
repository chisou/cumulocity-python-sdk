# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris

from __future__ import annotations

import pytest

from pyc8y.auth import JWT, BasicAuth, BearerAuth, parse_auth
from tests.utils import b64encode, sample_jwt, build_auth_string


@pytest.mark.parametrize('auth_value, tenant_id', [
    (b64encode('t12345/some@domain.com:password'), 't12345'),
    (sample_jwt(sub='someuser@domain.com', ten='t12345'), 't12345'),
])
def test_get_tenant_id(auth_value, tenant_id):
    """Verify that the tenant ID can be resolved from any Auth instance."""
    auth = parse_auth(build_auth_string(auth_value))
    assert auth.get_tenant_id() == tenant_id


@pytest.mark.parametrize('auth_value', [
    b64encode('some@domain.com:password'),
])
def test_get_tenant_id_bad(auth_value):
    """Verify that a missing tenant ID in the authorization information
    results in a ValueError."""
    auth = parse_auth(build_auth_string(auth_value))
    with pytest.raises(Exception):
        auth.get_tenant_id()


@pytest.mark.parametrize('auth_value, username', [
    (b64encode('t12345/some@domain.com:password'), 'some@domain.com'),
    (b64encode('someone@domain.com:password'), 'someone@domain.com'),
    (sample_jwt(sub='someuser@domain.com', ten='t12345'), 'someuser@domain.com'),
])
def test_get_username(auth_value, username):
    """Verify that the username can be resolved from any Auth instance."""
    auth = parse_auth(build_auth_string(auth_value))
    assert auth.get_username() == username


def test_parse_auth_basic():
    """Verify that a BASIC authentication string can be parsed."""
    auth_value = b64encode('t123/some@domain.com:password')

    auth1 = BasicAuth.parse(auth_value)
    assert auth1.username == 't123/some@domain.com'

    auth2 = parse_auth(build_auth_string(auth_value))
    assert isinstance(auth2, BasicAuth)
    assert auth2.username == auth1.username


def test_parse_auth_bearer():
    """Verify that a BEARER authentication string can be parsed."""
    auth_value = sample_jwt(ten='t543', sub='someuser@domain.com')

    auth1 = BearerAuth.parse(auth_value)
    jwt1 = JWT(auth1.token)
    assert jwt1.tenant_id == 't543'
    assert jwt1.username == 'someuser@domain.com'

    auth2 = parse_auth(build_auth_string(auth_value))
    assert isinstance(auth2, BearerAuth)
    jwt2 = JWT(auth2.token)
    assert jwt2.tenant_id == jwt1.tenant_id
    assert jwt2.username == jwt1.username
