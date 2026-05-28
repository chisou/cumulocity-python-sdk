# Copyright (c) 2026 Christoph Souris


from typing import AsyncIterator, Self, Sequence

from pyc8y.model.application import Application
from pyc8y.model.model_base import (
    CumulocityObject,
    CumulocityResource,
    WithId,
    json_property,
    datetime_property,
    map_params,
    resolve_page_size,
)
from pyc8y.rest import CumulocityRestClient
from pyc8y.types import TenantMeta


class Tenant(WithId, CumulocityObject):
    """Represents a tenant within the database.

    Instances of this class are returned by functions of the corresponding
    Tenant API. Use this class to create new or update tenants.

    See also: https://cumulocity.com/api/core/#tag/Tenants
    """

    _meta = TenantMeta

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        *,
        domain: str | None = None,
        admin_email: str | None = None,
        admin_name: str | None = None,
        admin_pass: str | None = None,
        company: str | None = None,
        contact_name: str | None = None,
        contact_phone: str | None = None,
    ):
        super().__init__(c8y)
        self.domain = domain
        self.admin_email = admin_email
        self.admin_name = admin_name
        self.admin_pass = admin_pass
        self.company = company
        self.contact_name = contact_name
        self.contact_phone = contact_phone

    creation_time = json_property("creationTime", read_only=True)
    creation_datetime = datetime_property("creationTime")
    domain = json_property("domain")
    admin_email = json_property("adminEmail")
    admin_name = json_property("adminName")
    admin_pass = json_property("adminPass")
    company = json_property("company")
    contact_name = json_property("contactName")
    contact_phone = json_property("contactPhone")
    status = json_property("status", read_only=True)
    parent = json_property("parent", read_only=True)

    @property
    def applications(self) -> list[Application]:
        """Return all referenced Application objects as a list."""
        refs = self._source_json.get("applications", {}).get("references", [])
        return [Application.from_json(ref["application"], c8y=self.c8y) for ref in refs]

    @property
    def owned_applications(self) -> list[Application]:
        """Return all owned Application objects as a list."""
        from pyc8y.model.application import Application

        refs = self._source_json.get("ownedApplications", {}).get("references", [])
        return [Application.from_json(ref["application"], c8y=self.c8y) for ref in refs]

    async def create(self) -> Self:
        """Create a new representation of this tenant within the database.

        Returns:
            A fresh Tenant instance representing the created tenant.
        """
        return await self._create()

    async def update(self, copy: bool = False) -> Self:
        """Write changes to the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated Tenant. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._update(copy)

    async def reload(self, copy: bool = False) -> Self:
        """Reload changes from the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The reloaded Tenant. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._reload(copy)

    async def delete(self) -> None:
        """Delete this tenant from the database."""
        await self._delete()


class Tenants(CumulocityResource[Tenant]):
    """Provides access to the Tenants API.

    This class can be used for get, search for, create, update and
    delete tenants within the Cumulocity database.

    See also: https://cumulocity.com/api/core/#tag/Tenants
    """

    _meta = TenantMeta
    _object_type = Tenant

    async def get_current(self) -> Tenant:
        """Retrieve the current tenant.

        Returns:
            Tenant instance
        """
        json = await self.c8y.get("tenant/currentTenant")
        return Tenant.from_json(json, c8y=self.c8y)

    async def get(self, tenant_id: str) -> Tenant:
        """Read a specific tenant from the database.

        Args:
            tenant_id (str):  Database ID of the tenant

        Returns:
            Tenant object
        """
        return await self._get(tenant_id)

    def select(
        self,
        expression: str | None = None,
        *,
        parent: str | None = None,
        domain: str | None = None,
        company: str | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[Tenant]:
        """Query the database for tenants and iterate over the results.

        Args:
            expression (str):  Arbitrary filter expression; all other filters
                are ignored if this is provided
            parent (str):  ID of the parent tenant
            domain (str):  Tenant domain
            company (str):  Tenant's assigned company name
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int):  Pull a specific page only
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of Tenant instances
        """
        page_size = resolve_page_size(page_size, limit)
        params = (
            map_params(
                parent=parent,
                domain=domain,
                company=company,
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
            as_values=as_values,
            workers=workers,
            preserve_order=False,
        )

    async def get_all(
        self,
        expression: str | None = None,
        *,
        parent: str | None = None,
        domain: str | None = None,
        company: str | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[Tenant]:
        """Query the database for tenants and return the results as list.

        See `select` for a documentation of arguments.

        Returns:
            List of Tenant instances
        """
        return [
            x
            async for x in self.select(
                expression=expression,
                parent=parent,
                domain=domain,
                company=company,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
                **kwargs,
            )
        ]

    async def create(self, *tenants: Tenant, workers: int | None = None) -> None:
        """Create tenant objects within the database.

        Args:
            *tenants (Tenant):  Collection of Tenant instances
            workers (int):  Number of parallel workers
        """
        await self._create(*tenants, workers=workers)

    async def update(self, *tenants: Tenant, workers: int | None = None) -> None:
        """Update tenant objects within the database.

        Args:
            *tenants (Tenant):  Collection of Tenant instances
            workers (int):  Number of parallel workers
        """
        await self._update(*tenants, workers=workers)

    async def delete(self, *tenants: str | Tenant, workers: int | None = None) -> None:
        """Delete tenant objects from the database.

        Args:
            *tenants (str | Tenant):  Collection of Tenant instances or IDs
            workers (int):  Number of parallel workers
        """
        await self._delete(*tenants, workers=workers)
