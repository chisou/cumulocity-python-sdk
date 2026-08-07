# Copyright (c) 2026 Christoph Souris

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Sequence, TypeVar

from pyc8y.rest import BatchError
from pyc8y.base_util import encode_odata_query_value, ensure_sequence
from pyc8y.model.managed_object import Availability, ManagedObject, Device, DeviceGroup
from pyc8y.model.matcher import JsonMatcher
from pyc8y.model.model_base import (
    expression_implies_order,
    CumulocityResource,
    map_params,
    resolve_page_size,
    run_batched,
    ensure_ids,
)
from pyc8y.types import InventoryMeta


@dataclass
class ObjectReference:
    id: str
    name: str

    @classmethod
    def to_json(cls, object_id):
        return {"managedObject": {"id": str(object_id)}}


def references_property(key: str) -> property:
    def getter(self):
        return [ObjectReference(x["id"], x.get("name", None)) for x in self._source_json[key]["references"]]

    return property(getter)


MO = TypeVar("MO", bound="ManagedObject")


class Inventory(CumulocityResource[MO]):
    _meta = InventoryMeta
    _object_type = ManagedObject

    async def get(
        self,
        id: str,  # noqa
        *,
        with_children: bool | None = None,
        with_children_count: bool | None = None,
        skip_children_names: bool | None = None,
        with_parents: bool | None = None,
        with_latest_values: bool | None = None,
        **kwargs,
    ) -> MO:
        """Retrieve a specific object from the database.

        Args:
            id (str): Cumulocity ID of the object
            with_children (bool):  Whether children with ID and name should be
                included with each returned object
            with_children_count (bool): When set to true, the returned result
                will contain the total number of children in the respective
                child additions, assets and devices sub fragments.
            skip_children_names (bool):  If true, returned references of child
                devices won't contain their names.
            with_parents (bool): Whether to include a device's parents.
            with_latest_values (bool):  If true the platform includes the
                fragment `c8y_LatestMeasurements, which contains the latest
                measurement values reported by the device to the platform.

        Returns:
             The referenced object.

        Raises:
            KeyError:  if the ID is not defined within the database.
        """
        return await self._get(
            id,
            with_children=with_children,
            with_children_count=with_children_count,
            skip_children_names=skip_children_names,
            with_parents=with_parents,
            with_latest_values=with_latest_values,
            **kwargs,
        )

    async def get_by(
        self,
        expression: str | None = None,
        *,
        query: str | None = None,
        ids: Sequence[str] | None = None,
        order_by: str | None = None,
        type: str | None = None,
        parent: str | None = None,
        fragment: str | None = None,
        fragments: str | Sequence[str] | None = None,
        name: str | None = None,
        owner: str | None = None,
        text: str | None = None,
        only_roots: bool | None = None,
        with_children: bool | None = None,
        with_children_count: bool | None = None,
        skip_children_names: bool | None = None,
        with_groups: bool | None = None,
        with_parents: bool | None = None,
        with_latest_values: bool | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        **kwargs,
    ) -> MO:
        """Query the database for a specific object.

        This function is a special version of the `select` function assuming a single
        result being returned by the query.

        Returns:
            The specified object.

        Raises:
            ValueError:  if the query did not return any or more than one result.
        """
        result = await self.get_all(
            expression=expression,
            query=query,
            ids=ids,
            order_by=order_by,
            type=type,
            parent=parent,
            fragment=fragment,
            fragments=fragments,
            name=name,
            owner=owner,
            text=text,
            only_roots=only_roots,
            with_children=with_children,
            with_children_count=with_children_count,
            skip_children_names=skip_children_names,
            with_groups=with_groups,
            with_parents=with_parents,
            with_latest_values=with_latest_values,
            page_size=2,
            as_values=as_values,
            **kwargs,
        )
        if len(result) == 1:
            return result[0]
        raise ValueError(
            "No matching object found." if not result else "Ambiguous query; multiple matching objects found."
        )

    async def get_count(
        self,
        expression: str | None = None,
        *,
        query: str | None = None,
        ids: Sequence[str] | None = None,
        type: str | None = None,
        parent: str | None = None,
        fragment: str | None = None,
        fragments: str | Sequence[str] | None = None,
        name: str | None = None,
        owner: str | None = None,
        text: str | None = None,
        **kwargs,
    ) -> int:
        """Calculate the number of potential results of a database query.

        This function uses the same parameters as the `select` function.

        Returns:
            Number of potential results.
        """
        params = (
            map_params(
                **self._collate_filter_params(
                    query=query,
                    ids=ids,
                    type=type,
                    parent=parent,
                    fragment=fragment,
                    fragments=fragments,
                    name=name,
                    owner=owner,
                    text=text,
                    **kwargs,
                )
            )
            if not expression
            else {}
        )
        return await self._get_count(expression=expression, params=params)

    async def get_all(
        self,
        expression: str | None = None,
        *,
        query: str | None = None,
        ids: Sequence[str] | None = None,
        order_by: str | None = None,
        type: str | None = None,
        parent: str | None = None,
        fragment: str | None = None,
        fragments: str | Sequence[str] | None = None,
        name: str | None = None,
        owner: str | None = None,
        text: str | None = None,
        only_roots: bool | None = None,
        with_children: bool | None = None,
        with_children_count: bool | None = None,
        skip_children_names: bool | None = None,
        with_groups: bool | None = None,
        with_parents: bool | None = None,
        with_latest_values: bool | None = None,
        limit: int | None = 5,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[MO]:
        """Query the database for objects and return the results
        as list.

        This function is a greedy version of the `select` function. All
        available results are read immediately and returned as list.

        Returns:
            List of object instances or values/value tuples if
                the `as_values` parameter is defined,
        """
        return [
            x
            async for x in self.select(
                expression=expression,
                query=query,
                ids=ids,
                order_by=order_by,
                type=type,
                parent=parent,
                fragment=fragment,
                fragments=fragments,
                name=name,
                owner=owner,
                text=text,
                only_roots=only_roots,
                with_children=with_children,
                with_children_count=with_children_count,
                skip_children_names=skip_children_names,
                with_groups=with_groups,
                with_parents=with_parents,
                with_latest_values=with_latest_values,
                limit=limit,
                include=include,
                exclude=exclude,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
                **kwargs,
            )
        ]

    def select(  # not async, because it is just a pass-through. still returns an AsyncIterator
        self,
        expression: str | None = None,
        *,
        query: str | None = None,
        ids: Sequence[str] | None = None,
        order_by: str | None = None,
        type: str | None = None,
        parent: str | None = None,
        fragment: str | None = None,
        fragments: str | Sequence[str] | None = None,
        name: str | None = None,
        owner: str | None = None,
        text: str | None = None,
        only_roots: bool | None = None,
        with_children: bool | None = None,
        with_children_count: bool | None = None,
        skip_children_names: bool | None = None,
        with_groups: bool | None = None,
        with_parents: bool | None = None,
        with_latest_values: bool | None = None,
        limit: int | None = 5,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[MO]:
        """Query the database for objects and iterate over the results.

        This function is implemented in a lazy fashion - results will only be
        fetched from the database as long there is a consumer for them.

        Most parameters are considered to be filters, limiting the result set
        to objects which meet the filters specification.  Filters can be
        combined (within reason).

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            query (str):  Custom Cumulocity query string; if specified, all
                other filter parameters are ignored.
            ids (Sequence[str]): Sequence of database IDs to retrieve; if
                specified, all other filter parameters are ignored.
            order_by (str): Server-side ordering expression
                (e.g. `name asc`).
            type (str): Object type to filter by.
            parent (str): Database ID of a parent group/device; restricts
                results to direct children of this parent.
            fragment (str): Name of a present custom/standard fragment.
            fragments (str | Sequence[str]): Name or names of fragments;
                objects must have all listed fragments present. A single
                fragment name may be passed as a bare string.
            name (str): Exact name to filter by.
            owner (str): Username of the object's owner.
            text (str): Full-text search match.
            only_roots (bool): If true, only return objects without parents
                (root nodes of the inventory hierarchy).
            with_children (bool):  Whether children with ID and name should be
                included with each returned object.
            with_children_count (bool): When set to true, the returned result
                will contain the total number of children in the respective
                child additions, assets and devices sub fragments.
            skip_children_names (bool):  If true, returned references of child
                devices won't contain their names.
            with_groups (bool): Whether to include parent groups (asset
                parents) of each returned object.
            with_parents (bool): Whether to include a device's parents.
            with_latest_values (bool):  If true the platform includes the
                fragment `c8y_LatestMeasurements, which contains the latest
                measurement values reported by the device to the platform.
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            include (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The inclusion is applied first.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            exclude (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The exclusion is applied second.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int): Pull a specific page; this effectively disables
                automatic follow-up page retrieval.
            as_values: (*str|tuple):  Don't parse objects, but directly extract
                the values at certain JSON paths as tuples; If the path is not
                defined in a result, None is used; Specify a tuple to define
                a proper default value for each path.
            workers (int): Number of parallel page-fetch workers; if None,
                pages are fetched sequentially.

        Returns:
            Async iterator for object instances or values/value tuples if the
            `as_values` parameter is defined.

        See also: https://github.com/bytebutcher/pydfql/blob/main/docs/USER_GUIDE.md#4-query-language
        """
        page_size = resolve_page_size(page_size, limit, include, exclude)
        return self._select(
            expression=expression,
            query=query,
            ids=ids,
            order_by=order_by,
            type=type,
            parent=parent,
            fragment=fragment,
            fragments=fragments,
            name=name,
            owner=owner,
            text=text,
            only_roots=only_roots,
            with_children=with_children,
            with_children_count=with_children_count,
            skip_children_names=skip_children_names,
            with_groups=with_groups,
            with_parents=with_parents,
            with_latest_values=with_latest_values,
            limit=limit,
            include=include,
            exclude=exclude,
            page_size=page_size,
            page_number=page_number,
            as_values=as_values,
            workers=workers,
            **kwargs,
        )

    async def get_latest_availability(self, mo_id: str) -> Availability:
        """Retrieve the latest availability information of a managed object.

        Args:
            mo_id (str):  Device (managed object) ID

        Returns:
            DeviceAvailability object
        """
        return Availability(await self.c8y.get(f"{self.build_object_path(mo_id)}/availability"))

    async def get_supported_measurements(self, mo_id: str) -> list[str]:
        """Retrieve all supported measurements names of a specific managed
        object.

        Args:
            mo_id (str):  Managed object ID

        Returns:
            List of measurement fragment names.
        """
        result_json = await self.c8y.get(f"{self.build_object_path(mo_id)}/supportedMeasurements")
        return result_json["c8y_SupportedMeasurements"]

    async def get_supported_series(self, mo_id: str) -> list[str]:
        """Retrieve all supported measurement series names of a specific
        managed object.

        Args:
            mo_id (str):  Managed object ID

        Returns:
            List of series names.
        """
        result_json = await self.c8y.get(f"{self.build_object_path(mo_id)}/supportedSeries")
        return result_json["c8y_SupportedSeries"]

    async def create(self, *objects: MO, workers: int | None = None) -> None:
        return await self._create(*objects, workers=workers)

    async def update(self, *objects: MO, workers: int | None = None) -> None:
        return await self._update(*objects, workers=workers)

    async def apply_to(self, model: dict | MO, *objects: str | MO, workers: int | None = None) -> None:
        return await self._apply_to(model, *objects, workers=workers)

    async def delete(self, *objects: str | MO, workers: int | None = None) -> None:
        return await self._delete(*objects, workers=workers)

    def _select(
        self,
        expression: str | None = None,
        query: str | None = None,
        ids: Sequence[str] | None = None,
        order_by: str | None = None,
        type: str | None = None,
        parent: str | None = None,
        fragment: str | None = None,
        fragments: str | Sequence[str] | None = None,
        name: str | None = None,
        owner: str | None = None,
        text: str | None = None,
        limit: int | None = None,
        page_number: int | None = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[MO]:
        """Generic select function to be used by derived classes as well."""
        params = (
            map_params(
                **self._collate_filter_params(
                    query=query,
                    ids=ids,
                    order_by=order_by,
                    type=type,
                    parent=parent,
                    fragment=fragment,
                    fragments=fragments,
                    name=name,
                    owner=owner,
                    text=text,
                    **kwargs,
                )
            )
            if not expression
            else {}
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
            preserve_order=bool(order_by) or expression_implies_order(query) or expression_implies_order(expression),
        )

    def _collate_filter_params(
            self,
            query: str | None = None,
            ids: Sequence[str] | None = None,
            filters: Sequence[str] | None = None,
            order_by: str | None = None,
            type: str | None = None,
            parent: str | None = None,
            fragment: str | None = None,
            fragments: str | Sequence[str] | None = None,
            name: str | None = None,
            owner: str | None = None,
            text: str | None = None,
            **kwargs,
    ) -> dict:
        """Collate the various different filtering options."""
        only_devices = issubclass(self._object_type, Device)
        query_key = "q" if only_devices else "query"

        # if query is directly specified -> use it and ignore everything else
        if query:
            return {query_key: query, **kwargs}
        # if ids are directly specified -> use it and ignore everything else
        if ids:
            return {"ids": ids, **kwargs}

        # collate fragments; for device-only mode, ensure c8y_IsDevice is part of the filter
        multi_fragments = ensure_sequence(fragments or fragment)
        if only_devices:
            multi_fragments = ("c8y_IsDevice", *multi_fragments)
        single_fragment = multi_fragments[0] if len(multi_fragments) == 1 else None

        # we only need a query for filters that can't be expressed as direct
        # query parameters (a single fragment can, multiple fragments cannot)
        use_query = parent or filters or order_by or name or len(multi_fragments) > 1
        if not use_query:
            return {
                k: v
                for k, v in dict(type=type, owner=owner, text=text, fragment=single_fragment, **kwargs).items()
                if v is not None
            }

        # if any of the given filter is 'special' we have to convert to a query
        query_filters = list(filters) if filters else []

        if multi_fragments:
            query_filters.extend([f"has({x})" for x in multi_fragments])
        if parent:
            query_filters.append(f"bygroupid({parent})")
        if name:
            query_filters.append(f"name eq '{encode_odata_query_value(name)}'")
        if type:
            query_filters.append(f"type eq {type}")
        if owner:
            query_filters.append(f"owner eq {owner}")
        if text:
            query_filters.append(f"text eq '{encode_odata_query_value(text)}'")

        # convert to single query parameter
        order_by = f"+$orderby={order_by}" if order_by else ""
        query = f"$filter=({' and '.join(query_filters)}){order_by}"

        return {query_key: query, **kwargs}


class DeviceInventory(Inventory[Device]):
    """Provides access to the Device Inventory API.

    This class can be used for get, search for, create, update and
    delete device objects within the Cumulocity database.

    See also: https://cumulocity.com/api/#tag/Inventory-API
    """

    _object_type = Device

    async def request(self, id: str):  # noqa (id)
        """Create a device request.

        Args:
            id (str): Unique ID of the device (e.g. Serial, IMEI); this is
            _not_ the database ID.
        """
        await self.c8y.post("/devicecontrol/newDeviceRequests", json={"id": id})

    async def accept(self, id: str):  # noqa (id)
        """Accept a device request.

        Args:
            id (str): Unique ID of the device (e.g. Serial, IMEI); this is
            _not_ the database ID.
        """
        await self.c8y.put("/devicecontrol/newDeviceRequests/" + str(id), json={"status": "ACCEPTED"})

    async def delete(self, *devices: str | Device, workers: int | None = None) -> None:
        """Delete one or more devices and the corresponding within the database.

        The objects can be specified as instances of a database object
        (then, the id field needs to be defined) or simply as ID (integers
        or strings).

        Note: In contrast to the regular `delete` function defined in class
        ManagedObject, this version also removes the corresponding device
        user from database by invoking the `delete` function on the `Device`
        object which does this by default.

        Args:
            *devices (str | Device): Objects (or their database ID).
            workers (int): Number of workers to use for parallel processing
                or None to process sequentially.
        """
        if not workers:
            for d in devices:
                await d.delete()
            return

        errors: list[BaseException] = []
        for i in range(0, len(devices), workers):
            batch = devices[i : i + workers]
            results = await asyncio.gather(*(d.delete() for d in batch), return_exceptions=True)
            errors.extend(r for r in results if isinstance(r, BaseException))

        if errors:
            raise BatchError(errors)


class DeviceGroupInventory(Inventory):
    """Provides access to the Device Groups Inventory API.

    This class can be used for get, search for, create, update and
    delete device groups within the Cumulocity database.

    See also: https://cumulocity.com/api/#tag/Inventory-API
    """

    async def get_count(  # noqa (changed signature)
        self,
        expression: str | None = None,
        *,
        query: str | None = None,
        ids: Sequence[str] | None = None,
        parent: str | None = None,
        type: str | None = None,
        fragment: str | None = None,
        fragments: str | Sequence[str] | None = None,
        name: str | None = None,
        owner: str | None = None,
        text: str | None = None,
        **kwargs,
    ) -> int:
        # pylint: disable=arguments-differ, arguments-renamed
        type = type or (DeviceGroup.CHILD_TYPE if parent else None)
        if fragments or fragment:
            fragments = ["c8y_IsDeviceGroup", *ensure_sequence(fragments or [fragment])]
        else:
            fragment = "c8y_IsDeviceGroup"

        return await super().get_count(
            expression=expression,
            query=query,
            ids=ids,
            type=type,
            parent=parent,
            fragment=fragment,
            fragments=fragments,
            name=name,
            owner=owner,
            text=text,
            **kwargs,
        )

    def select(  # noqa (changed signature)
        self,
        expression: str | None = None,
        *,
        query: str | None = None,
        ids: Sequence[str] | None = None,
        order_by: str | None = None,
        type: str | None = None,
        parent: str | None = None,
        fragment: str | None = None,
        fragments: str | Sequence[str] | None = None,
        name: str | None = None,
        owner: str | None = None,
        text: str | None = None,
        only_roots: bool | None = None,
        with_children: bool | None = None,
        with_children_count: bool | None = None,
        skip_children_names: bool | None = None,
        with_groups: bool | None = None,
        with_parents: bool | None = None,
        with_latest_values: bool | None = None,
        limit: int | None = 5,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[DeviceGroup]:
        # pylint: disable=arguments-differ, arguments-renamed
        type = type or (DeviceGroup.CHILD_TYPE if parent else None)
        if fragments or fragment:
            fragments = ["c8y_IsDeviceGroup", *ensure_sequence(fragments or [fragment])]
        else:
            fragment = "c8y_IsDeviceGroup"

        return super().select(
            expression=expression,
            query=query,
            ids=ids,
            order_by=order_by,
            type=type,
            parent=parent,
            fragment=fragment,
            fragments=fragments,
            name=name,
            owner=owner,
            text=text,
            only_roots=only_roots,
            with_children=with_children,
            with_children_count=with_children_count,
            skip_children_names=skip_children_names,
            with_groups=with_groups,
            with_parents=with_parents,
            with_latest_values=with_latest_values,
            limit=limit,
            include=include,
            exclude=exclude,
            page_size=page_size,
            page_number=page_number,
            as_values=as_values,
            workers=workers,
            **kwargs,
        )

    async def assign_children(self, root_id: str, *child_ids: str, workers: int | None = None) -> None:
        """Link child groups to a device group.

        Args:
            root_id (str): ID of the root device group.
            *child_ids (str): IDs of the child device groups to assign.
            workers (int|None): Number of parallel requests; sequential if None.
        """
        path = f"{self.build_object_path(root_id)}/childAssets"
        await run_batched(
            list(child_ids),
            workers,
            lambda child_id: self.c8y.post(path, json=ObjectReference.to_json(child_id), accept=None),
        )

    async def unassign_children(self, root_id: str, *child_ids: str) -> None:
        """Unlink child groups from a device group.

        Args:
            root_id (str): ID of the root device group.
            *child_ids (str): IDs of the child device groups to unassign.
        """
        refs = {"references": [ObjectReference.to_json(child_id) for child_id in child_ids]}
        await self.c8y.request("DELETE", f"{self.build_object_path(root_id)}/childAssets", json=refs)

    async def delete_trees(self, *groups: str | DeviceGroup, workers: int | None = None) -> None:
        """Delete one or more device group trees from the database.

        Child groups are deleted recursively. This is equivalent to using
        the `cascade=true` parameter in the Cumulocity REST API.

        Args:
            *groups (str|DeviceGroup): Groups (or IDs) to delete.
            workers (int|None): Number of parallel requests; sequential if None.
        """
        await run_batched(
            ensure_ids(groups),
            workers,
            lambda x: self.c8y.request("DELETE", self.build_object_path(x), params={"cascade": "true"}),
        )
