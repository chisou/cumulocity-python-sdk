# Copyright (c) 2026 Christoph Souris

import asyncio
import getpass
import ssl
import sys
import time
from abc import abstractmethod, ABC
import logging
import os
from asyncio import Semaphore
from typing import Callable, Mapping, Self
from urllib.parse import urlparse

import aiohttp
import certifi
from cachetools import TTLCache

from pyc8y.auth import parse_auth, BearerAuth, BasicAuth, JWT
from pyc8y.client import CumulocityClient
from pyc8y.rest import Auth, UnauthorizedError, MissingTfaError, HttpError, CumulocityRestClient


log = logging.getLogger(__name__)

_undefined = object()  # sentinel to distinguish None from undefined parameters

_clients: dict[tuple, CumulocityClient] = {}


class _FancyFormatter(logging.Formatter):
    CONFIG = {
        logging.INFO: ("", "⏺"),
        logging.WARNING: ("\033[33m", "⚠️"),
        logging.ERROR: ("\033[31m", "❌"),
        logging.CRITICAL: ("\033[41m", "🚨"),
    }
    DEFAULT =  ("\033[37m", "•")
    RESET = '\033[0m'
    def format(self, record):
        config = self.CONFIG.get(record.levelno, self.DEFAULT)
        log_fmt = f"{config[0]}{config[1]}  %(name)-20s  %(message)s{self.RESET}"
        return logging.Formatter(log_fmt).format(record)


def _configure_logging(level: int | str) -> None:
    numeric = level if isinstance(level, int) else getattr(logging, level.upper())
    if numeric < logging.WARNING:
        logging.getLogger("pyc8y").setLevel(level)
    else:
        logging.getLogger().setLevel(level)
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_pyc8y_handler", False):
            root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_FancyFormatter())
    handler._pyc8y_handler = True
    root.addHandler(handler)


async def get_client(
    base_url: str | None = None,
    tenant_id: str | None = None,
    username: str | None = None,
    password: str | None = None,
    max_concurrent: int | None = None,
    log_level: int | str | None = None,
) -> CumulocityClient:
    """Get a ready to use CumulocityClient instance for use in interactive
    sessions.

    Reads connection details from standard¹ Cumulocity environment variables
    when not explicitly provided, and falls back to interactive prompts for
    anything still missing.

    ```python
    c8y = await get_client()
    ```

    Args:
        base_url (str):  Cumulocity base URL; reads C8Y_BASEURL if omitted.
        tenant_id (str):  Tenant ID; reads C8Y_TENANT if omitted.
        username (str):  Username; reads C8Y_USER if omitted.
        password (str):  Password; reads C8Y_PASSWORD if omitted.
        max_concurrent (int):  Maximum number of concurrent tasks.
        log_level (int|str):  If set, installs a colorized stdout handler
            on the root logger. Looser-than-default levels (DEBUG, INFO)
            are applied to the `pyc8y` logger only, so third-party libs
            stay quiet; stricter-than-default levels (ERROR, CRITICAL) are
            applied to the root logger to dampen everything. Enable other
            namespaces on demand with e.g.
            `logging.getLogger("aiohttp").setLevel(logging.DEBUG)`.

    ¹ See also the go-c8y-cli (https://goc8ycli.netlify.app/docs/concepts/sessions/#continuous-integration-usage-environment-variables)
    and Cumulocity microservice bootstrap (https://cumulocity.com/docs/microservice-sdk/general-aspects/#microservice-bootstrap)
    """
    if log_level is not None:
        _configure_logging(log_level)
    semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else None
    base_url = base_url or os.environ.get("C8Y_BASEURL")
    tenant_id = tenant_id or os.environ.get("C8Y_TENANT")
    username = username or os.environ.get("C8Y_USER")
    password = password or os.environ.get("C8Y_PASSWORD")
    auth = None

    def read_variable(env_name: str, prompt: str | None = None, secret: bool = False) -> str | None:
        if env_name in os.environ:
            return os.environ[env_name]
        if not prompt:
            return None
        return getpass.getpass(prompt) if secret else input(prompt)

    # (1) resolve what we can from a token in the environment
    token = os.environ.get("C8Y_TOKEN")
    if token:
        jwt = JWT(token)
        base_url = base_url or jwt.get_claim("aud")
        tenant_id = tenant_id or jwt.get_claim("ten")
        username = username or jwt.get_claim("sub")
        exp = int(jwt.get_claim("exp"))
        if time.time() <= (exp - 60 * 60):
            auth = BearerAuth(token)
        else:
            print("Access token found but invalidated as it was almost expired.")

    # (2) resolve remaining parameters (interactively if needed)
    base_url = base_url or read_variable("C8Y_BASEURL", "Please enter the Cumulocity base URL or hostname:")
    tenant_id = tenant_id or read_variable("C8Y_TENANT", "Please enter the Cumulocity tenant ID:")
    username = username or read_variable("C8Y_USER", "Please enter the Cumulocity username:")
    if base_url and not urlparse(base_url).scheme:
        base_url = f"https://{base_url}"
    assert base_url and tenant_id and username

    # (3) return cached client if one exists for these parameters
    client_key = (base_url, tenant_id, username)
    if client_key in _clients:
        return _clients[client_key]

    # (4) authenticate if still needed
    if not auth:
        needs_tfa = False
        while not auth:
            pw = password or read_variable("C8Y_PASSWORD", "Please enter the Cumulocity password:", secret=True)
            if not pw:
                raise UnauthorizedError("No password provided. Authentication failed.")
            tfa_code = input("Please enter a current TFA code:") if needs_tfa else None

            try:
                auth, _ = await CumulocityRestClient.authenticate(
                    base_url=base_url,
                    tenant_id=tenant_id,
                    username=username,
                    password=pw,
                    tfa_token=tfa_code,
                )
            except MissingTfaError:
                needs_tfa = True
            except HttpError:
                print(f"Invalid username or password (URL: {base_url}, User: {username}).")
                password = None

    # (5) init client and write to cache
    client = CumulocityClient(
        base_url=base_url,
        tenant_id=tenant_id,
        auth=auth,
        semaphore=semaphore,
    )
    _clients[client_key] = client
    return client


def c8y_keys() -> set[str]:
    """Provide the names of defined Cumulocity environment variables.

    Returns: A set of environment variable names, starting with 'C8Y_'
    """
    return set(filter(lambda x: "C8Y_" in x, os.environ.keys()))


def get_c8y_env(name: str, default: str | None = _undefined) -> str | None:  # type: ignore[assignment]
    """Try to read a specific Cumulocity environment variable.

    Args:
        name (str):  Environment variable key
        default (str):  Default value to use if key is not defined

    Returns:
        The value of the environment variable.

    Raises:
        ValueError:  (not KeyError!) if the variable is not present.
    """
    try:
        return os.environ[name]
    except KeyError as e:
        if default is not _undefined:
            return default
        keys = ", ".join(c8y_keys()) or "none"
        raise ValueError(f"Missing environment variable: {name}. Found {keys}.") from e



class _CumulocityAppBase(ABC):
    """Internal class, base for both Per Tenant and Multi Tenant specific
    implementation."""

    def __init__(self, log: logging.Logger, cache_size: int = 100, cache_ttl: int = 3600, **kwargs):
        super().__init__(**kwargs)
        self.log = log
        self.user_instances = TTLCache(maxsize=cache_size, ttl=cache_ttl)

    @abstractmethod
    def _build_user_instance(self, auth: Auth) -> CumulocityClient:
        """This must be defined by the implementing classes."""

    async def get_user_instance(
        self, headers: Mapping[str, str] | None = None, cookies: Mapping[str, str] | None = None
    ) -> CumulocityClient:
        """Return a user-specific CumulocityApi instance.

        The instance will have user access, based on the Authorization header
        provided in the headers dict or corresponding entries in the cookies
        dict. The instance will be built on demand, previously created instances
        are cached.

        Args:
            headers (Mapping): A dictionary of HTTP header entries. The user
                access is based on the Authorization header within.
            cookies (Mapping): A dictionary of HTTP Cookie entries. The user
                access is based on an authorization cookie as provided by
                Cumulocity.
        Returns:
            A CumulocityApi instance authorized for a named user.
        """
        if not (headers or cookies):
            raise RuntimeError("At least one of 'headers' or 'cookies' must be specified.")

        auth_info = self._get_auth_header(headers, cookies)
        try:
            return self.user_instances[auth_info]
        except KeyError:
            instance = self._build_user_instance(parse_auth(auth_info))
            self.user_instances[auth_info] = instance
            return instance

    async def clear_user_cache(self, username: str | None = None):
        """Manually clean the user sessions cache.

        Args:
            username (str):  Name of a specific user to remove or None
                to clean the cache completely
        """
        if not username:
            self.user_instances.clear()
            log.info("User cache cleared.")
        else:
            for auth_header, item in self.user_instances.items():
                if username == parse_auth(auth_header).get_username():
                    del item
                    log.info(f"User '{username}' cleared from cache.")

    async def close(self):
        """Release resources held by this app.

        Closes any cached per-user client sessions. Subclasses extend this
        to close their own additional resources (own session, tenant cache,
        shared connector).
        """
        for inst in list(self.user_instances.values()):
            await inst.close()
        self.user_instances.clear()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args):
        await self.close()

    @staticmethod
    def _get_auth_header(headers: Mapping[str, str] | None = None, cookies: Mapping[str, str] | None = None) -> str:
        """Extract the authorization information from headers and cookies."""
        headers = headers or {}
        cookies = cookies or {}

        header_auth = next((v for k, v in headers.items() if k.upper() == "AUTHORIZATION"), None)
        cookie_auth = next((v for k, v in cookies.items() if k.upper() == "AUTHORIZATION"), None)

        if cookie_auth:
            cookie_auth = f"Bearer {cookie_auth}"  # cookie auth is just a JWT

        if header_auth and cookie_auth and header_auth != cookie_auth:
            log.warning(
                "Conflicting Authorization values in headers "
                f"({header_auth}) and cookies ({cookie_auth}). Using cookie."
            )
        if cookie_auth:
            return cookie_auth
        if header_auth:
            return header_auth

        keys = ", ".join(dict.fromkeys([*headers.keys(), *cookies.keys()])) or "None"
        raise KeyError(f"Unable to resolve Authorization information. Found keys: {keys}.")

    @staticmethod
    def _get_env(name: str, default: str | None = _undefined) -> str | None:  # type: ignore[assignment]
        """Try to read a specific Cumulocity environment variable.

        Args:
            name (str):  Environment variable key
            default (str):  Default value to use if key is not defined

        Returns:
            The value of the environment variable.

        Raises:
            ValueError:  (not KeyError!) if the variable is not present.
        """
        try:
            return os.environ[name]
        except KeyError as e:
            if default is not _undefined:
                return default
            keys = ", ".join(c8y_keys()) or "none"
            raise ValueError(f"Missing environment variable: {name}. Found {keys}.") from e


class SimpleCumulocityApp(_CumulocityAppBase, CumulocityClient):
    """Application-like Cumulocity API.

    The SimpleCumulocityApp class is intended to be used as base within
    a single-tenant microservice hosted on Cumulocity. It evaluates the
    environment to the resolve the authentication information automatically.

    Note: This class should be used in Cumulocity microservices using the
    PER_TENANT authentication mode only. It will not function in environments
    using the MULTITENANT mode.

    The SimpleCumulocityApp class is an enhanced version of the standard
    `CumulocityClient` class. All Cumulocity functions can be used directly.
    Additionally, it can be used to provide `CumulocityClient` instances for
    specific named users via the `get_user_instance` function.
    """

    _log = logging.getLogger(__name__)

    def __init__(
            self,
            application_key: str | None = None,
            processing_mode: str | None = None,
            cache_size: int = 100,
            cache_ttl: int = 3600,
            max_concurrent: int | None = None,
    ):
        """Create a new tenant specific instance.

        Args:
            application_key (str): An application key to include in
                all requests for tracking purposes; this will be read from
                the environment (APPLICATION_KEY) if not defined.
            processing_mode (str);  Connection processing mode (see also
                https://cumulocity.com/api/core/#processing-mode)
            cache_size (int): The maximum number of cached user
                instances (if user instances are created at all).
            cache_ttl (int): An maximum cache time for user
                instances (if user instances are created at all).
            max_concurrent (int): The maximum number of concurrent
                tasks handed down to the underlying tenant.

        Returns:
            A new CumulocityApp instance
        """
        self._semaphore = Semaphore(max_concurrent) if max_concurrent else None
        baseurl = self._get_env("C8Y_BASEURL")
        tenant_id = self._get_env("C8Y_TENANT")
        # authentication is either token or username/password
        try:
            token = self._get_env("C8Y_TOKEN")
            assert token
            auth = BearerAuth(token)
        except ValueError:
            username = self._get_env("C8Y_USER")
            password = self._get_env("C8Y_PASSWORD")
            assert username and password
            auth = BasicAuth(f"{tenant_id}/{username}", password)
        if not application_key:
            application_key = self._get_env("APPLICATION_KEY", default=None)
        super().__init__(
            log=self._log,
            cache_size=cache_size,
            cache_ttl=cache_ttl,
            base_url=baseurl,
            tenant_id=tenant_id,
            auth=auth,
            application_key=application_key,
            processing_mode=processing_mode,
            semaphore=self._semaphore,
        )

    def _build_user_instance(self, auth) -> CumulocityClient:
        """Build a CumulocityApi instance for a specific user, using the
        same Base URL, Tenant ID and Application Key as the main instance."""
        return CumulocityClient(
            base_url=self.base_url,
            tenant_id=self.tenant_id,
            auth=auth,
            application_key=self.application_key,
            processing_mode=self.processing_mode,
            semaphore=self._semaphore,
        )

    async def close(self):
        """Close the app's own session and all cached per-user sessions."""
        await _CumulocityAppBase.close(self)
        await CumulocityRestClient.close(self)


class MultiTenantCumulocityApp(_CumulocityAppBase):
    """Multi-tenant enabled Cumulocity application wrapper.

    The MultiTenantCumulocityApp class is intended to be used as base within
    a multi-tenant microservice hosted on Cumulocity. It evaluates the
    environment to the resolve the bootstrap authentication information
    automatically.

    Note: This class is intended to be used in Cumulocity microservices
    using the MULTITENANT authentication mode. It will not function in
    PER_TENANT environments.

    The MultiTenantCumulocityApp class serves as a factory. It provides
    access to tenant-specific CumulocityApi instances via the
    `get_tenant_instance` function. A special bootstrap CumulocityApi
    instance is available via the `bootstrap_instance` property.
    """

    _log = logging.getLogger(__name__)

    def __init__(
        self,
        application_key: str | None = None,
        processing_mode: str | None = None,
        cache_size: int = 100,
        cache_ttl: int = 3600,
        connection_limit: int = 100,
        connection_limit_per_host: int = 0,
        max_concurrent: int | None = None,
    ):
        """Create a new instance.

        Args:
            application_key (str|None): An application key to include in
                all requests for tracking purposes; this will be read from
                the environment (APPLICATION_KEY) if not defined.
            processing_mode (str);  Connection processing mode (see also
                https://cumulocity.com/api/core/#processing-mode)
            cache_size (int|None): The maximum number of cached tenant
                instances (if tenant instances are created at all).
            cache_ttl (int|None): An maximum cache time for tenant
                instances (if tenant instances are created at all).
            connection_limit (int): Maximum number of simultaneous HTTP
                connections in the shared pool across all tenant/user
                clients.
            connection_limit_per_host (int): Maximum simultaneous
                connections to a single host; `0` means unlimited
                (bounded only by `connection_limit`).
            max_concurrent (int): The maximum number of concurrent
                tasks across all subscribed tenants.

        Returns:
            A new MultiTenantCumulocityApp instance
        """
        super().__init__(log=self._log, cache_size=cache_size, cache_ttl=cache_ttl)
        self.application_key = application_key or self._get_env("APPLICATION_KEY", default=None)
        self.processing_mode = processing_mode
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self._connection_limit = connection_limit
        self._connection_limit_per_host = connection_limit_per_host
        self._connector: aiohttp.BaseConnector | None = None
        self._connector_lock = asyncio.Lock()
        self._semaphore = Semaphore(max_concurrent) if max_concurrent else None
        self.bootstrap_instance = self._create_bootstrap_instance(
            application_key=self.application_key,
            processing_mode=self.processing_mode,
            connector_factory=self._get_connector,
            semaphore=self._semaphore,
        )
        self._subscribed_auths = TTLCache(maxsize=cache_size, ttl=cache_ttl)
        self._tenant_instances = TTLCache(maxsize=cache_size, ttl=cache_ttl)

    async def _get_connector(self) -> aiohttp.BaseConnector:
        """Lazily create the shared TCPConnector. Must be called from an
        async context (aiohttp connectors bind to the running loop).
        """
        connector = self._connector
        if connector is None:
            async with self._connector_lock:
                connector = self._connector
                if connector is None:
                    ssl_context = ssl.create_default_context(cafile=certifi.where())
                    connector = aiohttp.TCPConnector(
                        ssl=ssl_context,
                        limit=self._connection_limit,
                        limit_per_host=self._connection_limit_per_host,
                    )
                    self._connector = connector
        return connector

    async def _get_tenant_auth(self, tenant_id: str) -> Auth:
        """Cached access to auth information of subscribed tenants."""
        try:
            return self._subscribed_auths[tenant_id]
        except KeyError:
            self._subscribed_auths = await self._read_subscription_auths(self.bootstrap_instance)
            return self._subscribed_auths[tenant_id]

    @classmethod
    async def _read_subscriptions(cls, bootstrap_instance: CumulocityClient) -> list[dict]:
        """Read subscribed tenants details.

        Returns:
            A list of tenant details dicts.
        """
        subscriptions = await bootstrap_instance.get("/application/currentApplication/subscriptions")
        return subscriptions["users"]

    @classmethod
    async def _read_subscription_auths(cls, bootstrap_instance: CumulocityClient) -> dict[str, Auth]:
        """Read subscribed tenant's auth information.

        Returns:
            A dict of tenant auth information by ID
        """
        cache = {}
        for subscription in await cls._read_subscriptions(bootstrap_instance):
            tenant = subscription["tenant"]
            username = subscription["name"]
            password = subscription["password"]
            cache[tenant] = BasicAuth(f"{tenant}/{username}", password)
        return cache

    async def get_subscribers(self) -> list[str]:
        """Query the subscribed tenants.

        Returns:
            A list of tenant ID.
        """
        return [x["tenant"] for x in await self._read_subscriptions(self.bootstrap_instance)]

    def create_listener(
            self,
            callback: Callable[[set[str]], None] | None = None,
            sequential: bool = False,
            polling_interval: float = 3600,
            startup_delay: float = 60,
    ) -> "SubscriptionListener":
        """Create a subscription listener for this app.

        Args:
            callback (Callable): an async callback function to be invoked
                when the subscribers change; Use the `add_callback` function
                to add callbacks for individually added/removed subscribers.
            sequential (bool): If True, callbacks run one at a time (guarded
                by an asyncio.Lock). Default False — callbacks run
                concurrently as asyncio tasks.
            polling_interval (float): How often to poll for changes.
            startup_delay (float): How many seconds to wait after a
                subscriber change before invoking the callbacks.

        Returns:
            A SubscriptionListener instance.
        """
        return SubscriptionListener(
            app=self,
            callback=callback,
            sequential=sequential,
            polling_interval=polling_interval,
            startup_delay=startup_delay,
        )

    @classmethod
    def _create_bootstrap_instance(
        cls,
        application_key: str | None = None,
        processing_mode: str | None = None,
        connector_factory=None,
        semaphore: Semaphore | None = None,
    ) -> CumulocityClient:
        """Build the bootstrap instance from the environment."""
        base_url = cls._get_env("C8Y_BASEURL")
        tenant_id = cls._get_env("C8Y_BOOTSTRAP_TENANT")
        username = cls._get_env("C8Y_BOOTSTRAP_USER")
        password = cls._get_env("C8Y_BOOTSTRAP_PASSWORD")
        assert base_url and tenant_id and username and password
        return CumulocityClient(
            base_url=base_url,
            tenant_id=tenant_id,
            auth=BasicAuth(username, password),
            application_key=application_key,
            processing_mode=processing_mode,
            connector_factory=connector_factory,
            semaphore=semaphore,
        )

    async def _create_tenant_instance(self, tenant_id: str) -> CumulocityClient:
        """Build a tenant instance."""
        auth = await self._get_tenant_auth(tenant_id)
        return CumulocityClient(
            self.bootstrap_instance.base_url,
            tenant_id,
            auth=auth,
            application_key=self.application_key,
            processing_mode=self.processing_mode,
            connector_factory=self._get_connector,
            semaphore=self._semaphore,
        )

    def _build_user_instance(self, auth) -> CumulocityClient:
        """Build a CumulocityApi instance for a specific user."""
        tenant_id = auth.get_tenant_id()
        return CumulocityClient(
            base_url=self.bootstrap_instance.base_url,
            tenant_id=tenant_id,
            auth=auth,
            application_key=self.application_key,
            processing_mode=self.processing_mode,
            connector_factory=self._get_connector,
            semaphore=self._semaphore,
        )

    async def get_tenant_instance(
            self,
            tenant_id: str | None = None,
            headers: Mapping[str, str]  | None= None,
            cookies: Mapping[str, str] | None = None,
    ) -> CumulocityClient:
        """Provide access to a tenant-specific instance in a multi-tenant
        application setup.

        Args:
            tenant_id (str):  ID of the tenant to get access to
            headers (Mapping):  Inbound request headers, the tenant ID
                is resolved from the Authorization header
            cookies (Mapping): A dictionary of HTTP Cookie entries. The user
                access is based on an authorization cookie as provided by
                Cumulocity.

        Returns:
            A CumulocityApi instance authorized for a tenant user
        """
        if tenant_id:
            return await self._get_tenant_instance(tenant_id)

        if not (headers or cookies):
            raise RuntimeError("At least one of 'tenant_id', 'headers' or cookies must be specified.")

        auth_header = self._get_auth_header(headers, cookies)
        if not auth_header:
            raise ValueError("Missing authentication information. Unable to resolve tenant ID.")

        tenant_id = parse_auth(auth_header).get_tenant_id()
        return await self._get_tenant_instance(tenant_id)

    async def _get_tenant_instance(self, tenant_id: str) -> CumulocityClient:
        """Cached access to already built tenant instances."""
        try:
            return self._tenant_instances[tenant_id]
        except KeyError:
            instance = await self._create_tenant_instance(tenant_id)
            self._tenant_instances[tenant_id] = instance
            return instance

    async def close(self):
        """Close all sessions and the shared connection pool."""
        await super().close()  # user cache
        for inst in list(self._tenant_instances.values()):
            await inst.close()
        self._tenant_instances.clear()
        await self.bootstrap_instance.close()
        if self._connector is not None:
            await self._connector.close()


class SubscriptionListener:
    """Multi-tenant subscription listener.

    Polls the MultiTenantCumulocityApp for subscriber changes and invokes
    registered callbacks when tenants subscribe or unsubscribe.

    Note: Not thread-safe, expected to run in async code.
    """

    _n = 0

    def __init__(
        self,
        app: MultiTenantCumulocityApp,
        callback: Callable[[set[str]], None] | None = None,
        sequential: bool = False,
        polling_interval: float = 3600,
        startup_delay: float = 60,
    ):
        """Create a subscription listener.

        Args:
            app (MultiTenantCumulocityApp): The Cumulocity application
                managing subscribers.
            callback (Callable): an async callback function to be invoked
                when the subscribers change; Use the `add_callback` function
                to add callbacks for individually added/removed subscribers.
            sequential (bool): If True, callbacks run sequentially. Otherwise
                (default) callbacks run concurrently as asyncio tasks.
            polling_interval (float): How often to poll for changes.
            startup_delay (float): How many seconds to wait after a
                subscriber change before invoking the callbacks.
        """
        instance_id = f"[{SubscriptionListener._n}]" if SubscriptionListener._n > 0 else ""
        SubscriptionListener._n += 1
        self._instance_name = type(self).__name__ + instance_id
        self._log = logging.getLogger(__name__ + instance_id)
        self.app = app
        self.polling_interval = polling_interval
        self.startup_delay = startup_delay
        self.callbacks: list[Callable] = [callback] if callback else []
        self.callbacks_on_add: list[Callable] = []
        self.callbacks_on_remove: list[Callable] = []
        self._lock = asyncio.Lock() if sequential else None
        self._listen_task: asyncio.Task | None = None
        self._callback_tasks: set[asyncio.Task] = set()
        self._stop_event = asyncio.Event()

    async def __aenter__(self) -> Self:
        self.start()
        return self

    async def __aexit__(self, *args):
        self.stop()
        if self._listen_task:
            await self._listen_task

    def add_callback(
        self,
        callback: Callable[[str | set[str]], None],
        when: str = "any",
    ) -> Self:
        """Add a callback for subscription changes.

        Args:
            callback: Async function invoked on subscription changes. Receives
                a single tenant ID (str) for 'added'/'removed' events, or the
                full set of current subscriber IDs for 'any'/'always'.
            when: When to invoke the callback — 'added', 'removed', or
                'any'/'always' (default).

        Returns:
            self, to support chaining.
        """
        if when in {"always", "any"}:
            self.callbacks.append(callback)
        elif when == "added":
            self.callbacks_on_add.append(callback)
        elif when == "removed":
            self.callbacks_on_remove.append(callback)
        else:
            raise ValueError(f"Invalid activation mode: {when}")
        return self

    async def listen(self):
        """Run the subscription polling loop.

        Blocks until stop() is called or the task is cancelled.
        """
        if not self._listen_task:
            self._listen_task = asyncio.current_task()
        self._stop_event.clear()
        self._log.debug("Listener started.")

        async def serialized(cr):
            assert self._lock is not None
            async with self._lock:
                await cr

        async def invoke(fun, arg):

            def on_done(task):
                self._callback_tasks.discard(task)
                if not task.cancelled() and task.exception():
                    self._log.error(f"Uncaught exception in callback: {task.exception()}", exc_info=task.exception())

            if self._log.isEnabledFor(logging.DEBUG):
                self._log.debug(f"Invoking callback: {fun.__module__}.{fun.__name__}")
            coro = serialized(fun(arg)) if self._lock else fun(arg)
            callback_task = asyncio.create_task(coro)
            self._callback_tasks.add(callback_task)
            callback_task.add_done_callback(on_done)

        try:
            last_subscribers: set[str] = set()
            while not self._stop_event.is_set():
                loop_start = time.monotonic()

                current_subscribers = set(await self.app.get_subscribers())
                added = current_subscribers - last_subscribers
                removed = last_subscribers - current_subscribers

                for tenant_id in removed:
                    self._log.info(f"Tenant subscription removed: {tenant_id}.")
                    for cb in self.callbacks_on_remove:
                        await invoke(cb, tenant_id)

                if added and self.startup_delay:
                    elapsed = time.monotonic() - loop_start
                    delay = self.startup_delay - elapsed
                    if delay > 0:
                        await asyncio.sleep(delay)

                for tenant_id in added:
                    self._log.info(f"Tenant subscription added: {tenant_id}.")
                    for cb in self.callbacks_on_add:
                        await invoke(cb, tenant_id)

                if added or removed:
                    self._log.info(f"Current subscriptions: {', '.join(current_subscribers) or 'None'}.")
                    for cb in self.callbacks:
                        await invoke(cb, current_subscribers)

                last_subscribers = current_subscribers

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.polling_interval)
                    break  # stop() was called
                except asyncio.TimeoutError:
                    pass  # interval elapsed, poll again

        except Exception as e:
            self._log.error(f"Uncaught exception during listen: {e}", exc_info=e)
        finally:
            pending = self.get_callbacks()
            if pending:
                self._log.debug(f"Awaiting {len(pending)} ending callbacks.")
                await asyncio.gather(*pending)
        self._log.debug("Listener ended.")

    def start(self) -> asyncio.Task:
        """Start the listener as an asyncio Task.

        Returns:
            The created asyncio Task.
        """
        task = asyncio.create_task(self.listen(), name=self._instance_name)
        self._listen_task = task
        return task

    def stop(self):
        """Signal the listener to stop.

        Returns immediately without awaiting the listener to finish.
        """
        self._stop_event.set()

    def get_callbacks(self) -> list[asyncio.Task]:
        """Return currently running (not yet done) callback tasks."""
        return [t for t in self._callback_tasks if not t.done()]
