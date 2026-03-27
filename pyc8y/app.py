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


def c8y_keys() -> set[str]:
    """Provide the names of defined Cumulocity environment variables.

    Returns: A set of environment variable names, starting with 'C8Y_'
    """
    return set(filter(lambda x: 'C8Y_' in x, os.environ.keys()))


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

    def get_user_instance(self, headers: Mapping[str, str] = None, cookies: Mapping[str, str] = None) -> CumulocityClient:
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

        if header_auth and cookie_auth and header_auth != cookie_auth:
            log.warning("Conflicting Authorization values in headers "
                        f"({header_auth}) and cookies ({cookie_auth}). Using header.")
        if header_auth:
            return header_auth
        if cookie_auth:
            return cookie_auth

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
            keys = ', '.join(c8y_keys()) or "none"
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
            self,
            application_key: str = None,
            processing_mode: str = None,
            cache_size: int = 100,
            cache_ttl: int = 3600
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
        baseurl = self._get_env('C8Y_BASEURL')
        tenant_id = self._get_env('C8Y_TENANT')
        # authentication is either token or username/password
        try:
            token = self._get_env('C8Y_TOKEN')
            auth = BearerAuth(token)
        except ValueError:
            username = self._get_env('C8Y_USER')
            password = self._get_env('C8Y_PASSWORD')
            auth = BasicAuth(f'{tenant_id}/{username}', password)
        if not application_key:
            application_key = self._get_env('APPLICATION_KEY', default=None)
        super().__init__(log=self._log, cache_size=cache_size, cache_ttl=cache_ttl,
                         base_url=baseurl, tenant_id=tenant_id, auth=auth,
                         application_key=application_key, processing_mode=processing_mode)

    def _build_user_instance(self, auth) -> CumulocityClient:
        """Build a CumulocityApi instance for a specific user, using the
        same Base URL, Tenant ID and Application Key as the main instance."""
        return CumulocityClient(base_url=self.base_url, tenant_id=self.tenant_id, auth=auth,
                                application_key=self.application_key, processing_mode=self.processing_mode)

    def __aenter__(self) -> Self:
        return self


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

    def __init__(self, application_key: str = None,  processing_mode: str = None,
                 cache_size: int = 100, cache_ttl: int = 3600):
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
        self.application_key = application_key or self._get_env('APPLICATION_KEY', default=None)
        self.processing_mode = processing_mode
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self.bootstrap_instance = self._create_bootstrap_instance(
            application_key=self.application_key,
            processing_mode=self.processing_mode,
        )
        self._subscribed_auths = TTLCache(maxsize=cache_size, ttl=cache_ttl)
        self._tenant_instances = TTLCache(maxsize=cache_size, ttl=cache_ttl)

    def _get_tenant_auth(self, tenant_id: str) -> Auth:
        """Cached access to auth information of subscribed tenants."""
        try:
            return self._subscribed_auths[tenant_id]
        except KeyError:
            self._subscribed_auths = self._read_subscription_auths(self.bootstrap_instance)
            return self._subscribed_auths[tenant_id]

    @classmethod
    def _read_subscriptions(cls, bootstrap_instance: CumulocityClient) -> list[dict]:
        """Read subscribed tenants details.

        Returns:
            A list of tenant details dicts.
        """
        subscriptions = bootstrap_instance.get('/application/currentApplication/subscriptions')
        return subscriptions['users']

    @classmethod
    def _read_subscription_auths(cls, bootstrap_instance: CumulocityClient):
        """Read subscribed tenant's auth information.

        Returns:
            A dict of tenant auth information by ID
        """
        cache = {}
        for subscription in cls._read_subscriptions(bootstrap_instance):
            tenant = subscription['tenant']
            username = subscription['name']
            password = subscription['password']
            cache[tenant] = BasicAuth(f'{tenant}/{username}', password)
        return cache

    def get_subscribers(self) -> list[str]:
        """Query the subscribed tenants.

        Returns:
            A list of tenant ID.
        """
        return [x['tenant'] for x in self._read_subscriptions(self.bootstrap_instance)]

    @classmethod
    def _create_bootstrap_instance(cls, application_key: str = None, processing_mode: str = None) -> CumulocityClient:
        """Build the bootstrap instance from the environment."""
        base_url = cls._get_env('C8Y_BASEURL')
        tenant_id = cls._get_env('C8Y_BOOTSTRAP_TENANT')
        username = cls._get_env('C8Y_BOOTSTRAP_USER')
        password = cls._get_env('C8Y_BOOTSTRAP_PASSWORD')
        return CumulocityClient(
            base_url=base_url,
            tenant_id=tenant_id,
            auth = BasicAuth(username, password),
            application_key=application_key,
            processing_mode=processing_mode,
        )

    def _create_tenant_instance(self, tenant_id: str) -> CumulocityClient:
        """Build a tenant instance."""
        auth = self._get_tenant_auth(tenant_id)
        return CumulocityClient(self.bootstrap_instance.base_url, tenant_id, auth=auth,
                                application_key=self.application_key, processing_mode=self.processing_mode)

    def _build_user_instance(self, auth) -> CumulocityClient:
        """Build a CumulocityApi instance for a specific user, using the
        same Base URL, Tenant ID and Application Key as the main instance."""
        tenant_id = auth.get_tenant_id()
        return CumulocityClient(base_url=self.bootstrap_instance.base_url, tenant_id=tenant_id, auth=auth,
                                application_key=self.application_key, processing_mode=self.processing_mode)

    def get_tenant_instance(self, tenant_id: str = None,
                            headers: Mapping[str, str] = None, cookies: Mapping[str, str] = None) -> CumulocityClient:
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
        # (1) if the tenant ID is specified we just
        if tenant_id:
            return self._get_tenant_instance(tenant_id)

        # (2) otherwise, look for the Authorization header
        if not (headers or cookies):
            raise RuntimeError("At least one of 'tenant_id', 'headers' or cookies must be specified.")

        auth_header = self._get_auth_header(headers, cookies)
        if not auth_header:
            raise ValueError("Missing authentication information. Unable to resolve tenant ID.")

        tenant_id = parse_auth(auth_header).get_tenant_id()
        return self._get_tenant_instance(tenant_id)

    def _get_tenant_instance(self, tenant_id: str) -> CumulocityClient:
        """Cached access to already build tenant instances."""
        try:
            return self._tenant_instances[tenant_id]
        except KeyError:
            instance = self._create_tenant_instance(tenant_id)
            self._tenant_instances[tenant_id] = instance
            return instance

    def __enter__(self) -> Self:
        return self

    def __exit__(self, __exc_type, __exc_value, __traceback):
        pass


class CumulocityApp(CumulocityClient):
    """Cumulocity API wrapper to be used for interactive sessions.

    As a context manager it ensures that a valid Cumulocity connection is
    available at runtime.  It uses standard environment variables when
    defined (C8Y_BASEURL, C8Y_TENANT, C8Y_USER, C8Y_PASSWORD, as well
    as C8Y_TOKEN) and interactively requests updated information in case
    some data is missing.

    ```
    async with CumulocityApp() as c8y:
        alarms = await c8y.alarms.get_all(type="cx_MyAlarm")
        ...
    ```
    """

    _cached_passwords: dict[str, str] = {}

    @staticmethod
    def _read_variable(env_name: str, prompt: str = None, secret: bool = False):
        if env_name in os.environ:
            return os.environ[env_name]

        if not prompt:
            return None

        if secret:
            return getpass.getpass(prompt)
        return input(prompt)

    def __init__(self):
        base_url = None
        tenant_id = None
        username = None

        # (1) check if there is a token defined
        token = os.environ.get('C8Y_TOKEN', None)
        if token:
            jwt = JWT(token)
            # preserve info
            base_url = jwt.get_claim('aud')
            tenant_id = jwt.get_claim('ten')
            username = jwt.get_claim('sub')
            # check validity
            exp = int(jwt.get_claim('exp'))
            if time.time() > (exp - 60*60):
                print("Access token found, but invalidated as it was almost expired.")
                token = None

        # (2) no token (or invalidated)
        if not token:
            # read necessary info for auth, this can also be resolved from an invalid token
            base_url = base_url or self._read_variable(
                'C8Y_BASEURL',
                "Please enter the Cumulocity base URL or hostname:"
            )

            tenant_id = tenant_id or self._read_variable(
                'C8Y_TENANT',
                "Please enter the Cumulocity tenant ID:"
            )
            username = username or self._read_variable(
                'C8Y_USER',
                "Please enter the Cumulocity username:"
            )
            if not urlparse(base_url).scheme:
                base_url = f'https://{base_url}'

            # authenticate (in a loop in case of wrong passwords entered)
            needs_tfa = False
            while not token:
                # read password (might already been cached)
                password = self._cached_passwords.get(username, None)
                password = password or self._read_variable(
                    'C8Y_PASSWORD',
                    "Please enter the Cumulocity password:",
                    secret=True
                )
                # if no password is provided, exit the loop
                if not password:
                    raise UnauthorizedError("No password provided. Authentication failed.")
                # preserve password for next time
                self._cached_passwords[username] = password
                # request TFA code if needed
                tfa_code = input("Please enter a current TFA code:") if needs_tfa else None

                try:
                    token, _ = CumulocityRestClient.authenticate(
                        base_url=base_url,
                        tenant_id=tenant_id,
                        username=username,
                        password=password,
                        tfa_token=tfa_code,
                    )
                except MissingTfaError:
                    needs_tfa = True
                    # we can just go to the next loop iteration, password is cached
                    continue
                except HttpError:
                    print(f"Invalid username or password (URL: {base_url}, User: {username}).")
                    self._cached_passwords.pop(username, None)
                    continue

        # (1) build new connection from token and put to cache
        os.environ['C8Y_TOKEN'] = token
        super().__init__(base_url=base_url, tenant_id=tenant_id, auth=BearerAuth(token))

    def __aenter__(self) -> Self:
        super().__aenter__()
        return self

    def __aexit__(self, exc_type, exc_value, traceback):
        super().__aexit__(exc_type, exc_value, traceback)
        return True