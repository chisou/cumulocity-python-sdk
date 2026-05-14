# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris

# pylint: disable=protected-access

from __future__ import annotations

import os
import time
from unittest.mock import patch

import jwt
import pytest

from pyc8y.app import c8y_keys
from pyc8y.auth import JWT
from pyc8y.base_util import like, matches
from pyc8y.model.model_util import to_pascal_case


@pytest.mark.parametrize(
    'name, expected',
    [
        ('name', 'name'),
        ('pascal_case', 'pascalCase'),
        ('more_than_one', 'moreThanOne'),
        ('_leading_underscore', 'leadingUnderscore'),
    ])
def test_snake_to_pascal_case(name, expected):
    """Verify that snake case conversion works as expected."""
    assert to_pascal_case(name) == expected


@pytest.mark.parametrize(
    'expression, string, expected',
    [
        ('abc', 'abc', True),
        ('abc', 'abcd', False),
        ('*abc', 'abc', True),
        ('*abc', 'xabc', True),
        ('*abc', 'xabx', False),
        ('abc*', 'abc', True),
        ('abc*', 'abcx', True),
        ('abc*', 'abx', False),
        ('*abc*', 'abc', True),
        ('*abc*', 'xabcy', True),
        ('*abc*', 'xaby', False),
    ],
    ids=[
        'exact match',
        'no exact match',
        'ends with',
        'ends with #2',
        'no ends with',
        'starts with',
        'starts with #2',
        'no starts with',
        'contains',
        'contains #2',
        'no contains',
    ]
)
def test_like(expression, string, expected):
    """Verify that the `like` function works as expected."""
    assert like(expression, string) == expected


@pytest.mark.parametrize(
    'expression, string, expected',
    [
        ('abc', 'abc', True),
        ('abc', 'xabcy', True),
        (r'^abc$', 'xabcy', False),
        (r'abc.*', 'abcx', True),
    ],
    ids=[
        'exact match',
        'contains',
        'no full match',
        'regex match',
    ]
)
def test_matches(expression, string, expected):
    """Verify that the `matches` function works as expected."""
    assert matches(expression, string) == expected


@patch.dict(os.environ, {'C8Y_SOME': 'some', 'C8Y_THING': 'thing', 'C8YNOT': 'not'}, clear=True)
def test_c8y_keys():
    """Verify that the C8Y_* keys can be filtered from environment."""
    keys = c8y_keys()
    assert len(keys) == 2
    assert 'C8Y_SOME' in keys
    assert 'C8Y_THING' in keys


def create_jwt_token(tenant_id, hostname, username, valid_seconds=60) -> str:
    """Create a dummy JWT token as string."""
    payload = {
        'jti': None,
        'iss': hostname,
        'aud': hostname,
        'sub': username,
        'tci': '0722ff7b-684f-4177-9614-3b7949b0b5c9',
        'iat': int(time.time()),
        'nbf': int(time.time()),
        'exp': int(time.time()) + valid_seconds,
        'tfa': False,
        'ten': tenant_id,
        'xsrfToken': 'something',
    }
    return jwt.encode(payload, key='key')


@pytest.fixture(name='jwt_token')
def fixture_jwt_token() -> str:
    """Provide a sample JWT token as string."""
    return create_jwt_token('t12345', 't12345.cumulocity.com', 'some.user@cumulocity.com')


@pytest.fixture(name='jwt_token_bytes')
def fixture_jwt_token_bytes(jwt_token) -> bytes:
    """Provide a sample JWT token as bytes."""
    return jwt_token.encode('utf-8')


def test_resolve_tenant_id(jwt_token_bytes):
    """Verify that parsing the tenant ID from a Bearer authentication
    string works as expected."""
    assert JWT(jwt_token_bytes).tenant_id == 't12345'


def test_resolve_username(jwt_token_bytes):
    """Verify that parsing the username from a Bearer authentication
    string works as expected."""
    assert JWT(jwt_token_bytes).username == 'some.user@cumulocity.com'
