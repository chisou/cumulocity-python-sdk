# Copyright (c) 2026 Christoph Souris

import logging
import os
import sys
from typing import Any

import pytest
from dotenv import load_dotenv
from pytest_asyncio import is_async_test

from pyc8y.app import c8y_keys, SimpleCumulocityApp
from pyc8y.auth import BasicAuth
from pyc8y.client import CumulocityClient
from pyc8y.model import Device
from pyc8y.model.application import Application

from util.testing_util import create_random_name


# Configure logging
logging.getLogger('urllib3').setLevel(logging.DEBUG)
logging.getLogger('websockets').setLevel(logging.DEBUG)
logging.getLogger('pyc8y').setLevel(logging.DEBUG)


def pytest_collection_modifyitems(items):
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)



@pytest.fixture(scope='session', name="logger")
def fix_logger():
    """Provide a logger for testing."""
    handler = logging.StreamHandler(sys.__stderr__)
    logger = logging.getLogger('pyc8y.test')
    logging.getLogger('pyc8y').setLevel(logging.DEBUG)
    logging.getLogger("aiohttp.client").setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


@pytest.fixture(scope='session', name="safe_executor")
def fix_safe_executor(logger):
    """A safe function execution wrapper.

    This provides a `execute(fun)` function which catches/logs all
    exceptions. It returns True if the wrapped function was executed
    without error, False otherwise.
    """
    # pylint: disable=broad-except

    def execute(fun) -> bool:
        try:
            fun()
            return True
        except Exception as e:
            logger.warning(f"Caught exception ignored due to safe call: {e}")
        return False

    return execute

#
# @pytest.fixture(scope='function')
# def auto_delete(logger):
#     """Register a created Cumulocity object for automatic deletion after test function execution."""
#     # pylint: disable=broad-exception-caught
#     objects = []
#
#     def register(obj) -> Any:
#         objects.append(obj)
#
#     yield register
#
#     for o in objects:
#         try:
#             # Deletion should through a KeyError if object was already deleted
#             o.delete()
#         except KeyError:
#             pass
#         except Exception as e:
#             logger.warning(f"Caught exception ignored due to safe call: {e}")


@pytest.fixture(scope='session', name="test_environment")
def fix_test_environment(logger):
    """Prepare the environment, i.e. read a .env file if found."""

    # check if there is a .env file
    if os.path.exists('.env'):
        logger.info("Environment file (.env) exists and will be considered.")
        # check if any C8Y_ variable is already defined
        predefined_keys = c8y_keys()
        if predefined_keys:
            logger.fatal("The following environment variables are already defined and may be overridden: "
                         + ', '.join(predefined_keys))
        load_dotenv()
    # list C8Y_* keys
    defined_keys = c8y_keys()
    logger.info(f"Found the following keys: {', '.join(defined_keys)}.")


@pytest.fixture(scope='session', name="live_c8y")
async def fix_live_c8y(request, test_environment):
    """Provide a live CumulocityApi instance as defined by the environment."""
    if 'C8Y_BASEURL' not in os.environ:
        raise RuntimeError("Missing Cumulocity environment variables (C8Y_*). Cannot create CumulocityApi instance. "
                           "Please define the required variables directly or setup a .env file.")

    c8y = SimpleCumulocityApp()
    yield c8y
    await c8y.close()


@pytest.fixture(scope='function', name="safe_create")
async def fix_safe_create(logger, live_c8y, request):
    """Wrap a created Cumulocity object so that it will automatically be deleted
    after a test regardless of an exception or failure.

    Deletion is still expected by the test, so this will log a warning if the
    object was not deleted and needed to be cleaned up."""
    objects_with_node = []

    async def create_and_register(obj) -> Any:
        if not obj.c8y:
            obj.c8y = live_c8y
        o = await obj.create()
        objects_with_node.append((o, request.node.name))
        return o

    yield create_and_register

    for o, node in objects_with_node:
        try:
            # Deletion should through a KeyError if object was already deleted
            await o.delete()
            logger.warning(f"{type(o).__name__} object #{o.id} was not deleted by test '{node}'.")
        except KeyError:
            pass
        except BaseException as e:
            logger.error(f"Caught exception ignored due to safe call: {e} (node: {node})")


@pytest.fixture(scope="module", name="module_factory")
async def fix_module_factory(logger, live_c8y: CumulocityClient, request):
    """Provides a generic object factory function which ensures that created
    objects are removed after the module testing.

    Deletion is _not_ expected by the test code."""

    created = []

    async def factory_fun(new_obj):
        if not new_obj.c8y:
            new_obj.c8y = live_c8y
        created_obj = await new_obj.create()
        test_node = request.module.__name__
        logger.info(f"Created {created_obj.__class__.__name__} object #{created_obj.id} in module {test_node}.")
        created.append((created_obj, test_node))
        return created_obj

    yield factory_fun

    for obj, node in created:
        try:
            await obj.delete()
            logger.info(f"Removed {obj.__class__.__name__} #{obj.id} from module {node}.")
        except KeyError:
            logger.warning(f"{obj.__class__.__name__} object #{obj.id} (module {node}) could not be removed (not found).")


@pytest.fixture(scope="module", name="session_factory")
async def fix_session_factory(logger, live_c8y: CumulocityClient, request):
    """Provides a generic object factory function which ensures that created
    objects are removed after the module testing.

    Deletion is _not_ expected by the test code."""

    created = []

    async def factory_fun(new_obj, context_request=request):
        if not new_obj.c8y:
            new_obj.c8y = live_c8y
        created_obj = await new_obj.create()

        inner_node = context_request.module.__name__ if hasattr(context_request, "module") else "session"
        if hasattr(context_request, "function"):
            inner_node = f"{inner_node}:{context_request.function.__name__}"
        logger.info(f"Created {created_obj.__class__.__name__} object #{created_obj.id} in {inner_node} context.")
        created.append((created_obj, inner_node))
        return created_obj

    yield factory_fun

    for obj, node in created:
        try:
            await obj.delete()
            logger.info(f"Removed {obj.__class__.__name__} #{obj.id} from {node} context.")
        except KeyError:
            logger.warning(f"{obj.__class__.__name__} object #{obj.id} ({node} context) could not be removed (not found).")



@pytest.fixture(scope='session', name="app_factory")
async def fix_app_factory(logger, live_c8y: CumulocityClient):
    """Provide an application (microservice) factory which creates a
    microservice application within Cumulocity, registers itself as
    subscribed tenant and returns the application's bootstrap client.

    All created microservice applications are removed after the tests.
    The factory users must ensure the uniqueness of the application
    names within the entire test session.

    Args:
        logger:  (injected) test logger.
        live_c8y:  (injected) connection to a live Cumulocity instance; the
            user must be allowed to create microservice applications.

    Returns:
        An async factory function accepting parameters application name
        (string) and required roles (list of string).
    """
    created: list[Application] = []

    async def factory_fun(name: str, roles: list[str]) -> CumulocityClient:

        # (1) Verify this application is not registered, yet
        if await live_c8y.applications.get_all(name=name):
            raise ValueError(f"Microservice application named '{name}' seems to be already registered.")

        # (2) Create application stub in Cumulocity
        manifest_json = {
            'settings': [{'defaultValue': '', 'key': x} for x in ('keyA', 'keyB')],
            'settingsCategory': f"app-{name}",
        }
        app = await Application(
            live_c8y,
            name=name,
            key=f'{name}-key',
            type=Application.MICROSERVICE_TYPE,
            availability=Application.PRIVATE_AVAILABILITY,
            context_path=name,
            required_roles=roles,
        ).create()
        created.append(app)

        # (3) Subscribe to newly created microservice
        subscription_json = {'application': {'id': app.id}}
        await live_c8y.post(f'tenant/tenants/{live_c8y.tenant_id}/applications',
                            json=subscription_json)
        logger.info(f"Microservice application '{name}' (ID {app.id}) created. "
                    f"Tenant '{live_c8y.tenant_id}' subscribed.")

        # (4) Read bootstrap user details
        bootstrap_user_json = await live_c8y.get(f'application/applications/{app.id}/bootstrapUser')

        # (5) Create bootstrap instance
        bootstrap_c8y = CumulocityClient(
            base_url=live_c8y.base_url,
            tenant_id=bootstrap_user_json['tenant'],
            auth=BasicAuth(bootstrap_user_json['name'], bootstrap_user_json['password']),
        )
        logger.info(f"Bootstrap instance created. Tenant: {bootstrap_c8y.tenant_id}, "
                    f"User: {bootstrap_user_json['name']}")

        return bootstrap_c8y

    yield factory_fun

    # unregister applications
    for a in created:
        try:
            await a.delete()
            logger.info(f"Microservice application '{a.name}' (ID {a.id}) deleted.")
        except KeyError:
            logger.warning(f"Application #{a.id} could not be removed (not found).")


# @pytest.fixture(scope='function')
# def sample_object(logger, live_c8y, random_name, auto_delete):
#     """Provide a sample object which is automatically removed after test."""
#     obj = ManagedObject(live_c8y, name=random_name, type=random_name).create()
#     auto_delete(obj)
#     return obj
#
#
@pytest.fixture(scope='session', name="session_device")
async def fix_session_device(logger: logging.Logger, live_c8y: CumulocityClient):
    """Provide an sample device, just for testing purposes."""

    typename = create_random_name()
    device = await Device(live_c8y, type=typename, name=typename, com_cumulocity_model_Agent={}).create()
    logger.info(f"Created test device #{device.id}, name={device.name}")

    yield device

    await device.delete()
    logger.info(f"Deleted test device #{device.id}")
