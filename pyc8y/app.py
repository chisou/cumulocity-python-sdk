# Copyright (c) 2026 Christoph Souris

import getpass
import time
from abc import abstractmethod, ABC
import logging
import os
from typing import Mapping, Self
from urllib.parse import urlparse

from cachetools import TTLCache

from pyc8y.auth import parse_auth, BearerAuth, BasicAuth, JWT
from pyc8y.client import CumulocityClient
from pyc8y.rest import Auth, UnauthorizedError, MissingTfaError, HttpError, CumulocityRestClient

_sentinel = object()

log = logging.getLogger(__name__)

_clients: dict[tuple, CumulocityClient] = {}


def get_client(
    base_url: str | None = None,
    tenant_id: str | None = None,
    username: str | None = None,
    password: str | None = None,
):
    """Get a ready to use CumulocityClient instance for use in interactive
    sessions.

    Reads connection details from standard¹ Cumulocity environment variables
    when not explicitly provided, and falls back to interactive prompts for
    anything still missing.

    Supports both direct await and async context manager usage:

    ```python
    c8y = await get_client()

    async with get_client() as c8y:
        ...
    ```

    Args:
        base_url (str):  Cumulocity base URL; reads C8Y_BASEURL if omitted.
        tenant_id (str):  Tenant ID; reads C8Y_TENANT if omitted.
        username (str):  Username; reads C8Y_USER if omitted.
        password (str):  Password; reads C8Y_PASSWORD if omitted.

    ¹ See also the go-c8y-cli (https://goc8ycli.netlify.app/docs/concepts/sessions/#continuous-integration-usage-environment-variables)
    and Cumulocity microservice bootstrap (https://cumulocity.com/docs/microservice-sdk/general-aspects/#microservice-bootstrap)
    """
    base_url = base_url or os.environ.get("C8Y_BASEURL")
    tenant_id = tenant_id or os.environ.get("C8Y_TENANT")
    username = username or os.environ.get("C8Y_USER")
    password = password or os.environ.get("C8Y_PASSWORD")

    async def _get_client() -> CumulocityClient:
        nonlocal base_url, tenant_id, username, password
        auth = None

        def read_variable(env_name: str, prompt: str = None, secret: bool = False) -> str | None:
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
        )
        _clients[client_key] = client
        return client

    class Connection:
        def __init__(self, coro):
            self._coro = coro
            self._client: CumulocityClient | None = None

        def __await__(self):
            return self._coro.__await__()

        async def __aenter__(self) -> CumulocityClient:
            self._client = await self._coro
            await self._client.__aenter__()
            return self._client

        async def __aexit__(self, *args):
            if self._client:
                await self._client.__aexit__(*args)

    return Connection(_get_client())


def c8y_keys() -> set[str]:
    """Provide the names of defined Cumulocity environment variables.

    Returns: A set of environment variable names, starting with 'C8Y_'
    """
    return set(filter(lambda x: "C8Y_" in x, os.environ.keys()))


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

    def get_user_instance(
        self, headers: Mapping[str, str] = None, cookies: Mapping[str, str] = None
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

    def clear_user_cache(self, username: str = None):
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

    @staticmethod
    def _get_auth_header(headers: Mapping[str, str] = None, cookies: Mapping[str, str] = None) -> str:
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
    def _get_env(name: str, default: str | None = _sentinel) -> str:
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
            if default is not _sentinel:
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
    CumulocityApi class. All Cumulocity functions can be used directly.
    Additionally, it can be used to provide CumulocityApi instances for
    specific named users via the `get_user_instance` function.
    """

    _log = logging.getLogger(__name__)

    def __init__(
        self, application_key: str = None, processing_mode: str = None, cache_size: int = 100, cache_ttl: int = 3600
    ):
        """Create a new tenant specific instance.

        Args:
            application_key (str|None): An application key to include in
                all requests for tracking purposes; this will be read from
                the environment (APPLICATION_KEY) if not defined.
            processing_mode (str);  Connection processing mode (see also
                https://cumulocity.com/api/core/#processing-mode)
            cache_size (int|None): The maximum number of cached user
                instances (if user instances are created at all).
            cache_ttl (int|None): An maximum cache time for user
                instances (if user instances are created at all).

        Returns:
            A new CumulocityApp instance
        """
        baseurl = self._get_env("C8Y_BASEURL")
        tenant_id = self._get_env("C8Y_TENANT")
        # authentication is either token or username/password
        try:
            token = self._get_env("C8Y_TOKEN")
            auth = BearerAuth(token)
        except ValueError:
            username = self._get_env("C8Y_USER")
            password = self._get_env("C8Y_PASSWORD")
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
        )


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
        self, application_key: str = None, processing_mode: str = None, cache_size: int = 100, cache_ttl: int = 3600
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

        Returns:
            A new MultiTenantCumulocityApp instance
        """
        super().__init__(log=self._log, cache_size=cache_size, cache_ttl=cache_ttl)
        self.application_key = application_key or self._get_env("APPLICATION_KEY", default=None)
        self.processing_mode = processing_mode
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self.bootstrap_instance = self._create_bootstrap_instance(
            application_key=self.application_key,
            processing_mode=self.processing_mode,
        )
        self._subscribed_auths = TTLCache(maxsize=cache_size, ttl=cache_ttl)
        self._tenant_instances = TTLCache(maxsize=cache_size, ttl=cache_ttl)

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

    @classmethod
    def _create_bootstrap_instance(cls, application_key: str = None, processing_mode: str = None) -> CumulocityClient:
        """Build the bootstrap instance from the environment."""
        base_url = cls._get_env("C8Y_BASEURL")
        tenant_id = cls._get_env("C8Y_BOOTSTRAP_TENANT")
        username = cls._get_env("C8Y_BOOTSTRAP_USER")
        password = cls._get_env("C8Y_BOOTSTRAP_PASSWORD")
        return CumulocityClient(
            base_url=base_url,
            tenant_id=tenant_id,
            auth=BasicAuth(username, password),
            application_key=application_key,
            processing_mode=processing_mode,
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
        )

    async def get_tenant_instance(
        self, tenant_id: str = None, headers: Mapping[str, str] = None, cookies: Mapping[str, str] = None
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

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args):
        pass
