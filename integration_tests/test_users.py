# Copyright (c) 2026 Christoph Souris

import secrets
import string

import pytest

from pyc8y.auth import BasicAuth
from pyc8y.client import CumulocityClient
from pyc8y.model.user import User

from util.testing_util import create_random_name


def generate_password():
    """Generate a strong password meeting Cumulocity requirements."""
    alphabet = string.ascii_letters + string.digits + "_-.#&$"
    return "Aa0." + "".join(secrets.choice(alphabet) for _ in range(12))


async def test_crud(live_c8y: CumulocityClient):
    """Verify that basic CRUD functionality works."""
    username = create_random_name()
    email = f"{username}@cumulocity.gmbh"

    user = User(c8y=live_c8y, username=username, email=email, enabled=True)
    created_user = await user.create()
    try:
        assert created_user.id == username
        assert created_user.password_strength == "GREEN"
        assert created_user.require_password_reset
        assert created_user.tfa_enabled is False

        created_user.require_password_reset = False
        created_user.last_name = "last_name"
        updated_user = await created_user.update()

        assert updated_user.last_name == created_user.last_name
        assert updated_user.require_password_reset == created_user.require_password_reset
    finally:
        await created_user.delete()

    with pytest.raises(KeyError):
        await live_c8y.users.get(user.username)


async def test_select_by_name(live_c8y: CumulocityClient, safe_create):
    """Verify that user selection by name prefix works."""
    prefix = create_random_name()
    users = []
    for i in range(5):
        username = f"{prefix}-{i}"
        email = f"{username}@c8y.com"
        user = await safe_create(User(live_c8y, username=username, email=email, enabled=True))
        users.append(user)

    selected = await live_c8y.users.get_all(username=prefix)
    assert {x.id for x in selected} == {x.id for x in users}


async def test_select(live_c8y: CumulocityClient):
    """Verify that user selection by group works as expected."""
    # Group 2 (admin) should exist on all installations
    admin_users = await live_c8y.users.get_all(groups=["2"])
    assert admin_users

    # Spot-check: each result should actually belong to group 2
    for user in admin_users[:3]:
        groups = await live_c8y.user_groups.get_all(username=user.username)
        assert any(str(g.id) == "2" for g in groups)


async def test_get_current(live_c8y: CumulocityClient):
    """Verify that the current user can be read."""
    current1 = await live_c8y.users.get(live_c8y.username)
    current2 = await live_c8y.users.get_current()

    assert current1.username == current2.username


async def test_current_update(live_c8y: CumulocityClient, user_c8y: CumulocityClient):
    """Verify that updating the current user works as expected."""
    current_user = await user_c8y.users.get_current()

    current_user.first_name = "New"
    current_user = await current_user.update()
    assert current_user.first_name == "New"


@pytest.mark.skip(reason="TOTP methods not yet implemented in pyc8y")
async def test_current_totp(live_c8y: CumulocityClient, user_c8y: CumulocityClient):
    """Verify that the TOTP settings can be updated for the current user."""
    pass


async def test_current_set_password(live_c8y: CumulocityClient, user_c8y: CumulocityClient):
    """Verify that the password of the current user can be changed."""
    user = await user_c8y.users.get_current()

    # password strength requirements are enforced before updating
    with pytest.raises(Exception):
        await user.update_password(user_c8y.auth.password, "pw")

    # store last password change timestamp
    before_datetime = user.last_password_change_datetime

    # changing to a strong password should succeed
    new_password = generate_password()
    await user.update_password(user_c8y.auth.password, new_password)

    # password change timestamp must have been updated
    user = await user_c8y.users.get_current()
    assert user.last_password_change_datetime != before_datetime

    # follow-up requests with the new password should still work
    await user_c8y.users.get_current()


async def test_set_owner(live_c8y: CumulocityClient, user_factory):
    """Verify that the owner of a user can be set and removed."""
    user1, _ = await user_factory()
    user2, _ = await user_factory()

    # set owner using the OO method
    await user1.set_owner(user2.username)
    db_user1 = await live_c8y.users.get(user1.username)
    assert db_user1.owner == user2.username

    # unset owner using the resource function
    await live_c8y.users.set_owner(user1.username, None)
    db_user1 = await live_c8y.users.get(user1.username)
    assert not db_user1.owner


async def test_set_delegate(live_c8y: CumulocityClient, user_factory):
    """Verify that the delegate of a user can be set and removed."""
    user, _ = await user_factory()
    current_username = live_c8y.auth.get_username()

    # set delegate using the OO method
    await user.set_delegate(current_username)
    db_user = await live_c8y.users.get(user.username)
    assert db_user.delegated_by == current_username

    # unset delegate using the resource function
    await live_c8y.users.set_delegate(user.username, None)
    db_user = await live_c8y.users.get(user.username)
    assert not db_user.delegated_by


async def test_get_tfa_settings(live_c8y: CumulocityClient, user_c8y: CumulocityClient):
    """Verify that the TFA settings can be retrieved."""
    tfa_settings = await live_c8y.users.get_tfa_settings(user_c8y.username)
    assert tfa_settings
    assert not tfa_settings.enabled


@pytest.fixture(scope="function")
async def user_factory(live_c8y: CumulocityClient):
    """Create users with passwords and remove them after the test."""
    created_users = []

    async def factory_fun() -> tuple[User, str]:
        username = create_random_name(2)
        email = f"{username}@cumulocity.gmbh"
        password = generate_password()
        user = await User(c8y=live_c8y, username=username, password=password, email=email).create()
        created_users.append(user)
        return user, password

    yield factory_fun

    for u in created_users:
        try:
            await u.delete()
        except KeyError:
            pass


@pytest.fixture(scope="function")
async def user_c8y(live_c8y: CumulocityClient, user_factory):
    """Provide a Cumulocity connection authenticated as a fresh test user."""
    new_user, password = await user_factory()
    c8y = CumulocityClient(
        base_url=live_c8y.base_url,
        tenant_id=live_c8y.tenant_id,
        auth=BasicAuth(new_user.username, password),
    )
    yield c8y
    await c8y.close()
