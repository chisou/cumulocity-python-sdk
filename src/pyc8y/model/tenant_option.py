# Copyright (c) 2026 Christoph Souris

from typing import AsyncIterator, Self, Sequence

from pyc8y.rest import CumulocityRestClient
from pyc8y.model.model_base import (
    CumulocityObject,
    CumulocityResource,
    json_property,
    map_params,
    resolve_page_size,
    run_batched,
)
from pyc8y.types import TenantOptionMeta


def build_category_resource(category: str) -> str:
    return f"{TenantOptionMeta.resource_path}/{category}"


def build_value_resource(category: str, key: str) -> str:
    return f"{TenantOptionMeta.resource_path}/{category}/{key}"


class TenantOption(CumulocityObject):
    """Represents a tenant option within the database.

    Instances of this class are returned by functions of the corresponding
    Tenant Options API. Use this class to create new or update options.

    See also: https://cumulocity.com/api/core/#tag/Options
    """

    _meta = TenantOptionMeta

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        *,
        category: str | None = None,
        key: str | None = None,
        value: str | None = None,
        encrypted: bool | None = None,
    ):
        super().__init__(c8y)
        self.category = category
        self.value = value
        self._key = f"credentials.{key}" if encrypted else key

    category = json_property("category")
    _key = json_property("key")

    @property
    def key(self) -> str | None:
        return self._key.removeprefix("credentials.")

    @property
    def is_encrypted(self) -> bool:
        return self._key.startswith("credentials.")

    @property
    def value(self):
        # value might be undefined, hence a special getter is needed
        return self.get("value", None)

    @value.setter
    def value(self, value: str):
        # value might be undefined, hence a special setter is needed
        self.set("value", value)

    async def create(self) -> Self:
        """Create a new representation of this option within the database.

        Returns:
            A fresh TenantOption instance representing the created option.
        """
        return await self._create()

    async def update(self, copy: bool = False) -> Self:
        """Write changes to the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated TenantOption. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        self._assert_c8y()
        if not self.category or not self.key:
            raise ValueError("Both option category and key must be set to allow direct object access.")
        result_json = await self.c8y.put(
            resource=build_value_resource(self.category, self._key),
            json={"value": self.value},
            accept=self._meta.object_mime_type,
            content_type=self._meta.object_mime_type,
        )
        if copy:
            return self._build(result_json, c8y=self.c8y)
        self._source_json = result_json
        self._staged_json = {}
        return self

    async def reload(self, copy: bool = False) -> Self:
        """Reload this option from the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).
        """

    async def delete(self) -> None:
        """Remove the option from the database."""
        self._assert_c8y()
        if not self.category or not self.key:
            raise ValueError("Both option category and key must be set to allow direct object access.")
        await self.c8y.delete(build_value_resource(self.category, self._key))


class TenantOptions(CumulocityResource[TenantOption]):
    """Provides access to the Tenant Options API.

    This class can be used for get, search for, create, update and
    delete tenant options within the Cumulocity database.

    See also: https://cumulocity.com/api/core/#tag/Options
    """

    _meta = TenantOptionMeta
    _object_type = TenantOption

    def build_object_path(self, category: str, key: str) -> str:  # noqa (signature differs)
        """Build the path to a specific tenant option.

        Args:
            category (str):  Option category
            key (str):  Option key (name)

        Returns:
            The relative path to the option within Cumulocity.
        """
        return f"{self.resource_path}/{category}/{key}"

    async def get(self, category: str, key: str) -> TenantOption:  # noqa (signature differs)
        """Retrieve a specific option from the database.

        Note: The key must be prefixed with `credentials.` in order to
        retrieve an encrypted option.

        Args:
            category (str):  Option category
            key (str):  Option key (name)

        Returns:
            A TenantOption instance
        """
        json = await self.c8y.get(self.build_object_path(category, key))
        return TenantOption.from_json(json, c8y=self.c8y)

    def select(
        self,
        expression: str | None = None,
        *,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
    ) -> AsyncIterator[TenantOption]:
        """Query the database for tenant options and iterate over the results.

        When `category` is provided, a single targeted request is made
        instead of using standard pagination.

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int):  Pull a specific page only
            as_values: (str|tuple|list[str|tuple]):  Don't parse objects, but
                directly extract the values at certain JSON paths as tuples;
                If the path is not defined in a result, None is used; Specify
                a tuple to define a proper default value for each path.
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of TenantOption objects or object values if
            as_values is specified,
        """
        page_size = resolve_page_size(page_size, limit)
        params = map_params(page_size=page_size) if not expression else ()
        return self._iterate(
            expression=expression,
            params=params,
            page_number=page_number,
            limit=limit,
            as_values=as_values,
            workers=workers,
        )

    async def get_all(
        self,
        expression: str | None = None,
        *,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_map: bool = False,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
    ) -> list[TenantOption] | dict[str, str] | dict[str, dict[str, str]]:
        """Query the database for tenant options and return the results as list.

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided
            limit (int):  Limit the number of results
            page_size (int):  Number of records read per request
            page_number (int):  Pull a specific page only
            as_map(bool): Whether the categories should be returned as dict
                of keys and values (grouped by category if category is not
                specified). Defaults to False.
            as_values: (str|tuple|list[str|tuple]):  Don't parse objects, but
                directly extract the values at certain JSON paths as tuples;
                If the path is not defined in a result, None is used; Specify
                a tuple to define a proper default value for each path.
            workers (int):  Number of parallel page-fetch workers

        Returns:
            List of TenantOption instances or dictionary of key/value pairs
            grouped by category.
        """
        if as_map and as_values:
            raise ValueError("Only one of as_values and as_map can be specified.")
        result = [
            x
            async for x in self.select(
                expression=expression,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
            )
        ]
        if not as_map:
            return result
        r = {}
        for o in result:
            r.setdefault(o.category, {})[o.key] = o.value
        return r

    async def get_value(self, category: str, key: str) -> str:
        """Retrieve the value of a specific option from the database.

        Note: The key must be prefixed with `credentials.` in order to
        retrieve an encrypted option.

        Args:
            category (str):  Option category
            key (str):  Option key (name)

        Returns:
            The value of the specified option
        """
        json = await self.c8y.get(self.build_object_path(category, key))
        return json["value"]

    async def get_values(self, category: str) -> dict[str, str]:
        """Retrieve all values for a specific category from the database.

        Note: The keys of encrypted tenant options is automatically stripped
        from the `credentials.` prefix.

        Args:
            category (str):  Option category

        Returns:
            The option values mapped by their key.
        """
        return await self.c8y.get(build_category_resource(category))

    async def update_values(self, category: str, values: dict[str, str]) -> None:
        """Update existing option's values within the database.

        Note: The key must be prefixed with `credentials.` in order to update
        an encrypted option.

        Args:
            category (str):  Option category
            values (dict[str, str]): Option values by key
        """
        await self.c8y.put(build_category_resource(category), json=values)  # application/json

    async def set_value(self, category: str, key: str, value: str) -> None:
        """Create an option within the database.

        Note: The key must be prefixed with `credentials.` in order to update
        an encrypted option.

        Args:
            category (str):  Option category
            key (str):  Option key (name)
            value (str):  Option value
        """
        await self.create(TenantOption(category=category, key=key, value=value))

    async def create(self, *options: TenantOption, workers: int | None = None) -> None:
        """Create options within the database.

        Args:
            *options (TenantOption):  Collection of TenantOption instances
        """
        await self._create(*options, workers=workers)

    async def update(self, *options: TenantOption, workers: int | None = None) -> None:
        """Update options within the database.

        Args:
            *options (TenantOption):  Collection of TenantOption instances
            workers (int):  Number of parallel workers
        """
        await run_batched(
            options,
            workers,
            lambda o: self.c8y.put(
                self.build_object_path(o.category, o._key),
                json=o._staged_json,
                accept=None,
            ),
        )

    async def delete(
        self,
        *options: TenantOption,
        category: str | None = None,
        key: str | None = None,
        workers: int | None = None,
    ) -> None:
        """Delete options within the database.

        A single tenant option object can be deleted by specifying parameters
        `category` and 'key' directly.
        Alternatively, a collection of TenantOption objects can be created
        in a single call, optionally specifying the number of parallel
        worker threads.

        Args:
            *options (TenantOption):  Collection of TenantOption instances
            category (str):  Option category
            key (str):  Option key (name)
            workers (int): The number of parallel processes to use
        """
        if not options:
            if not (category and key):
                raise ValueError("Both option category and key must be set to allow direct object access.")
            await self.c8y.delete(build_value_resource(category, key))
        else:
            await run_batched(options, workers, lambda o: self.delete(category=o.category, key=o.key))
