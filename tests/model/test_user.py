# Copyright (c) 2025 Cumulocity GmbH
# Copyright (c) 2026 Christoph Souris
# pylint: disable=redefined-outer-name

import datetime
import json
import os

import pytest

from pyc8y.model.user import User, CurrentUser, TfaSettings


@pytest.fixture(scope='function')
def sample_user() -> User:
    """Provide a sample user, read from JSON file."""
    path = os.path.dirname(__file__) + '/user.json'
    with open(path, encoding='utf-8', mode='rt') as f:
        user_json = json.load(f)

    return User.from_json(user_json)


def test_parsing():
    """Verify that parsing a User from JSON works."""

    # 1) read a sample user from file
    path = os.path.dirname(__file__) + '/user.json'
    with open(path, encoding='utf-8', mode='rt') as f:
        user_json = json.load(f)

    user = User.from_json(user_json)

    # 2) verify that all parsed fields match the file counterpart
    assert user.id == user_json['id']
    assert user.username == user_json['userName']
    assert user.email == user_json['email']
    assert user.enabled == user_json['enabled']
    assert user.display_name == user_json['displayName']
    assert user.first_name == user_json['firstName']
    assert user.last_name == user_json['lastName']
    assert user.password_strength == user_json['passwordStrength']
    assert user.tfa_enabled == user_json['twoFactorAuthenticationEnabled']
    assert user.require_password_reset == user_json['shouldResetPassword']


def test_current_parsing():
    """Verify that parsing a "current" User from JSON works."""

    # 1) read a sample user from file
    path = os.path.dirname(__file__) + '/current_user.json'
    with open(path, encoding='utf-8', mode='rt') as f:
        user_json = json.load(f)

    user = CurrentUser.from_json(user_json)

    # 2) verify that all parsed fields match the file counterpart
    #    including fields from abstract base class
    assert user.id == user_json['id']
    assert user.username == user_json['userName']
    assert user.email == user_json['email']


def test_tfa_settings_parsing():
    """Verify that TFA settings can be parsed from JSON as expected."""
    data = {"tfaEnabled": True,
            "tfaEnforced": True,
            "strategy": "TOTP",
            "lastTfaRequestTime": "2022-08-01T20:00:00.123Z"}

    tfa_settings = TfaSettings(data)
    assert tfa_settings.enabled == data['tfaEnabled']
    assert tfa_settings.enforced == data['tfaEnforced']
    assert tfa_settings.strategy == data['strategy']
    assert tfa_settings.last_request_time == data['lastTfaRequestTime']


def test_tfa_settings_formatting():
    """Verify that TFA settings can be formatted to JSON as expected."""
    now = datetime.datetime.now(datetime.timezone.utc)
    tfa_settings = TfaSettings()
    tfa_settings.enabled = True
    tfa_settings.enforced = True
    tfa_settings.strategy = 'SMS'
    tfa_settings.last_request_time = now

    # TfaSettings is a dict subclass — assertions are made directly against it
    assert tfa_settings['tfaEnabled'] is True
    assert tfa_settings['tfaEnforced'] is True
    assert tfa_settings['strategy'] == 'SMS'
    assert 'lastTfaRequestTime' in tfa_settings
