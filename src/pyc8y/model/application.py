# Copyright (c) 2025 Cumulocity GmbH

from typing import AsyncIterator, Self, Sequence

import aiohttp

from pyc8y.base_util import first
from pyc8y.model.matcher import JsonMatcher
from pyc8y.model.model_base import CumulocityObject, CumulocityResource, JsonObject, json_property, map_params, resolve_page_size
from pyc8y.rest import CumulocityRestClient
from pyc8y.types import ApplicationMeta, FileSpec, MimeType


class Application(CumulocityObject):
    """Represent an instance of an application object in Cumulocity.

    Instances of this class are returned by functions of the corresponding
    API. Use this class to create new or update objects.

    See also: https://cumulocity.com/api/#tag/Application-API
    """

    _meta = ApplicationMeta

    EXTERNAL_TYPE = "EXTERNAL"
    HOSTED_TYPE = "HOSTED"
    MICROSERVICE_TYPE = "MICROSERVICE"

    PRIVATE_AVAILABILITY = "PRIVATE"
    MARKET_AVAILABILITY = "MARKET"

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        *,
        name: str | None = None,
        key: str | None = None,
        type: str | None = None,  # noqa (type)
        availability: str | None = None,
        context_path: str | None = None,
        manifest: dict | None = None,
        roles: list[str] | None = None,
        required_roles: list[str] | None = None,
        breadcrumbs: bool | None = None,
        content_security_policy: str | None = None,
        dynamic_options_url: str | None = None,
        global_title: str | None = None,
        legacy: bool | None = None,
        right_drawer: bool | None = None,
        upgrade: bool | None = None,
        **kwargs,
    ):
        """Create a new Application object.

        Args:
            c8y (CumulocityRestClient):  Cumulocity connection reference; needs
                to be set for direct manipulation (create, delete)
            name (str):  Name of the application
            key (str):  Key to identify the application
            type (str):  Type of the application
            availability (str):  Application access level for tenants
            context_path (str):  The path where the application is accessible
            manifest (dict):  Microservice or web application manifest
            roles (list[str]):  List of roles provided by the application
            required_roles (list[str]):  List of roles required by the application
            breadcrumbs (bool):  Whether the (web) application uses breadcrumbs
            content_security_policy (str):  The content security policy of the application
            dynamic_options_url (str):  A URL to a JSON object with dynamic content options
            global_title (str):  The global title of the application
            legacy (bool):  Whether the (web) application is of legacy type
            right_drawer (bool):  Whether the (web) application uses the right hand context menu
            upgrade (bool):  Whether the (web) application uses both Angular and AngularJS
        """
        super().__init__(c8y, **kwargs)
        self.name = name
        self.key = key
        self.type = type
        self.availability = availability
        self.context_path = context_path
        self.manifest = manifest
        self.roles = roles
        self.required_roles = required_roles
        self.breadcrumbs = breadcrumbs
        self.content_security_policy = content_security_policy
        self.dynamic_options_url = dynamic_options_url
        self.global_title = global_title
        self.legacy = legacy
        self.right_drawer = right_drawer
        self.upgrade = upgrade

    name = json_property("name")
    key = json_property("key")
    type = json_property("type")
    availability = json_property("availability")
    context_path = json_property("contextPath")
    manifest = json_property("manifest")
    roles = json_property("roles")
    required_roles = json_property("requiredRoles")
    breadcrumbs = json_property("breadcrumbs")
    content_security_policy = json_property("contentSecurityPolicy")
    dynamic_options_url = json_property("dynamicOptionsUrl")
    global_title = json_property("globalTitle")
    legacy = json_property("legacy")
    right_drawer = json_property("rightDrawer")
    upgrade = json_property("upgrade")
    active_version_id = json_property("activeVersionId", read_only=True)

    @property
    def owner(self) -> str | None:
        """Tenant ID of the application owner (read-only)."""
        try:
            return self.json["owner"]["tenant"]["id"]
        except (KeyError, TypeError):
            return None

    async def create(self) -> Self:
        """Create the Application within the database.

        Returns:
            A fresh Application object representing what was
            created within the database (including the ID).
        """
        return await self._create()

    async def update(self, copy: bool = False) -> Self:
        """Update the Application within the database.

        Note: This will only send changed fields to increase performance.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated Application. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._update(copy)

    async def delete(self, **_) -> None:
        """Delete the Application within the database."""
        await self._delete()

    def resolve_tenant_option_category(self) -> str | None:
        """Resolve the tenant option category.

        The application's tenant option category is defined by the
        application's _settings category_ (as defined in its manifest), the
        application's name (as defined in its manifest), or the application's
        context path. The function chooses the first defined.

        Returns:
            The application's tenant option category.

        See also https://cumulocity.com/api/core/#operation/postOptionCollectionResource,
        _Encrypted credentials_
        """
        return first(
            self.get("manifest.settingsCategory"),
            self.get("manifest.name"),
            self.get("contextPath"),
            None,
        )


class ApplicationSubscription(JsonObject):
    """Represent current application subscriptions within Cumulocity.

    Instances of this class are returned by functions of the `Applications`
    API.

    See also: https://cumulocity.com/api/core/#tag/Current-application
    """

    tenant_id = json_property[str]("tenant", read_only=True)
    username = json_property[str]("name", read_only=True)
    password = json_property[str]("password", read_only=True)


class Applications(CumulocityResource[Application]):
    """Provides access to the Application API.

    This class can be used to get, search for, create, update and
    delete applications within the Cumulocity database.

    See also: https://cumulocity.com/api/#tag/Application-API
    """

    _meta = ApplicationMeta
    _object_type = Application

    async def get(self, application_id: str) -> Application:
        """Retrieve a specific application from the database.

        Args:
            application_id (str):  The database ID of the application

        Returns:
            An Application instance representing the object in the database.
        """
        return await self._get(application_id)

    async def get_current(self) -> Application:
        """Retrieve the current application.

        Note: Requires bootstrap permissions.

        Returns:
            An Application instance.
        """
        return Application.from_json(
            await self.c8y.get("application/currentApplication"),
            c8y=self.c8y,
        )

    async def get_current_settings(self) -> dict[str, str]:
        """Query the database for the current application's settings,
        i.e. tenant options.

        The tenant option category is determined by application's
        _settings category_, _name_ or _context path_.

        Note: Requires bootstrap permissions or service user permissions.

        Caveat: this function does _not_ remove the `credentials.` prefix
        of encrypted tenant options.


        Returns:
            Dictionary of tenant option values by key.

        See also: TenantOptions.get_values to read tenant options
        """
        return await self.c8y.get("application/currentApplication/settings", accept=MimeType.TENANT_OPTION)

    async def get_current_subscriptions(self) -> list[ApplicationSubscription]:
        """Query the database for subscriptions of the current application.

        Note: Requires bootstrap permissions.

        Returns:
            List of ApplicationSubscription instances.
        """
        result = await self.c8y.get("application/currentApplication/subscriptions", accept=MimeType.APPLICATION_USER_COLLECTION)
        return [ApplicationSubscription(x) for x in result["users"]]

    def select(
        self,
        expression: str | None = None,
        *,
        name: str | None = None,
        type: str | None = None,  # noqa (type)
        owner: str | None = None,
        user: str | None = None,
        tenant: str | None = None,
        subscriber: str | None = None,
        provided_for: str | None = None,
        has_versions: bool | None = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[Application]:
        """Query the database for applications and iterate over the results.

        This function is implemented in a lazy fashion - results will only be
        fetched from the database as long as there is a consumer for them.

        All parameters are considered to be filters, limiting the result set
        to objects which meet the filters' specification. Filters can be
        combined (within reason).

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            name (str):  Name of an application (no wildcards allowed)
            type (str):  Application type (e.g. HOSTED)
            owner (str):  ID of a Cumulocity user which owns the application
            user (str):  ID of a Cumulocity user which has general access
            tenant (str):  ID of a Cumulocity tenant which either owns the
                application or is subscribed to it
            subscriber (str):  ID of a Cumulocity tenant which is subscribed
                to the application (and may own it)
            provided_for (str):  ID of a Cumulocity tenant which is subscribed
                to the application but does not own it
            has_versions (bool):  Whether to filter for applications with a
                defined applicationVersions field
            include (str | JsonMatcher):  Matcher/expression to filter the query
                results (on client side). The inclusion is applied first.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            exclude (str | JsonMatcher):  Matcher/expression to filter the query
                results (on client side). The exclusion is applied second.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int):  Pull a specific page; this effectively disables
                automatic follow-up page retrieval.
            as_values (*str|tuple):  Don't parse objects, but directly extract
                the values at certain JSON paths as tuples.

        Returns:
            AsyncIterator of Application objects
        """
        page_size = resolve_page_size(page_size, limit, include, exclude)
        params = (
            map_params(
                name=name,
                type=type,
                owner=owner,
                user=user,
                tenant=tenant,
                subscriber=subscriber,
                provided_for=provided_for,
                has_versions=has_versions,
                page_size=page_size,
                **kwargs,
            )
            if not expression
            else ()
        )
        return self._iterate(
            expression=expression,
            params=params,
            page_number=page_number,
            limit=limit,
            include=include,
            exclude=exclude,
            as_values=as_values,
            workers=workers,
            preserve_order=False,
        )

    async def get_all(
        self,
        expression: str | None = None,
        *,
        name: str | None = None,
        type: str | None = None,  # noqa (type)
        owner: str | None = None,
        user: str | None = None,
        tenant: str | None = None,
        subscriber: str | None = None,
        provided_for: str | None = None,
        has_versions: bool | None = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[Application]:
        """Query the database for applications and return the results as list.

        This function is a greedy version of the `select` function. All
        available results are read immediately and returned as list.

        See `select` for a documentation of arguments.

        Returns:
            List of Application objects
        """
        return [
            x
            async for x in self.select(
                expression=expression,
                name=name,
                type=type,
                owner=owner,
                user=user,
                tenant=tenant,
                subscriber=subscriber,
                provided_for=provided_for,
                has_versions=has_versions,
                include=include,
                exclude=exclude,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
                **kwargs,
            )
        ]

    async def create(self, *applications: Application, workers: int | None = None) -> None:
        """Create application objects within the database.

        Args:
            *applications (Application):  Collection of Application instances
            workers (int):  The number of parallel processes to use
        """
        await self._create(*applications, workers=workers)

    async def update(self, *applications: Application, workers: int | None = None) -> None:
        """Update application objects within the database.

        Args:
            *applications (Application):  Collection of Application instances
            workers (int):  The number of parallel processes to use
        """
        await self._update(*applications, workers=workers)

    async def delete(self, *applications: str | Application, workers: int | None = None) -> None:
        """Delete application objects within the database.

        Args:
            *applications (str|Application):  Collection of Application instances or IDs
            workers (int):  The number of parallel processes to use
        """
        await self._delete(*applications, workers=workers)

    async def upload_attachment(self, application_id: str, file: FileSpec) -> None:
        """Upload application binary for a registered application.

        Args:
            application_id (str):  The Cumulocity object ID of the application
            file (str | PathLike | BinaryIO):  File path or file-like object to upload.

        See also: https://cumulocity.com/api/#tag/Application-binaries
        """
        import os

        path = self.build_object_path(application_id) + "/binaries"

        if isinstance(file, str):
            filename = os.path.basename(file)
            with open(file, "rb") as f:
                form = aiohttp.FormData()
                form.add_field("file", f, filename=filename, content_type="application/octet-stream")
                session = await self.c8y.session
                async with session.post(path, data=form) as r:
                    if r.status not in (200, 201):
                        raise ValueError(f"Failed to upload attachment. Status: {r.status}, Response: {await r.text()}")
        else:
            filename = getattr(file, "name", "binary")
            form = aiohttp.FormData()
            form.add_field("file", file, filename=os.path.basename(filename), content_type="application/octet-stream")
            session = await self.c8y.session
            async with session.post(path, data=form) as r:
                if r.status not in (200, 201):
                    raise ValueError(f"Failed to upload attachment. Status: {r.status}, Response: {await r.text()}")
