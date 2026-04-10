# Copyright (c) 2026 Christoph Souris

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Self, AsyncGenerator, Any, AsyncIterator, Sequence, TypeVar

from c8y_api.model import JsonMatcher
from pyc8y.rest import CumulocityRestClient, BatchError
from pyc8y.base_util import encode_odata_query_value, sanitize_page_size, flatten
from pyc8y.model.managed_object import ManagedObject, Device, DeviceGroup
from pyc8y.model.model_base import (
    CumulocityObject,
    json_property,
    time_property,
    datetime_property,
    assert_c8y,
    assert_id,
    tag_property,
    CumulocityResource,
    map_params,
    CO,
)
from pyc8y.types import MimeType, InventoryMeta, AsValuesSpec


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


@dataclass
class Availability:
    """Cumulocity availability status labels"""

    class ConnectionStatus:
        """Connection status labels"""

        CONNECTED = "CONNECTED"
        DISCONNECTED = "DISCONNECTED"

    class DataStatus:
        """Data status labels"""

        AVAILABLE = "AVAILABLE"
        UNAVAILABLE = "UNAVAILABLE"

    def __init__(self, json):
        self._json = json

    device_id = json_property("deviceId", read_only=True)
    external_id = json_property("externalId", read_only=True)
    connection_status = json_property("connectionStatus", read_only=True)
    data_status = json_property("dataStatus", read_only=True)
    last_message = json_property("lastMessage", read_only=True)
    last_message_time = json_property("lastMessage", read_only=True)
    last_message_datetime = datetime_property("lastMessage")
    interval = json_property("interval", read_only=True)

    @property
    def interval_minutes(self) -> int:
        """Return the required update interval in minutes as integer."""
        return int(self.interval.split(" ", 1)[0])


# class OtherManagedObject(CumulocityObject):
#     """ Represent a managed object within the database.
#
#     Instances of this class are returned by functions of the corresponding
#     Inventory API. Use this class to create new or update managed objects.
#
#     Within Cumulocity a managed object is used to hold virtually any
#     *additional* (apart from measurements, events and alarms) information.
#     This custom information is modelled in *fragments*, named elements
#     of any structure.
#
#     Fragments are modelled as standard Python fields and can be accessed
#     directly if the names & structures are known:
#
#         x = mo.c8y_CustomFragment.values.x
#
#     Managed objects can be changed and such updates are written as
#     *differences* to the database. The API does the tracking of these
#     differences automatically - just use the ManagedObject class like
#     any other Python class.
#
#         mo.owner = 'admin@cumulocity.com'
#         mo.c8y_CustomFragment.region = 'EMEA'
#         mo.add_fragment('c8y_CustomValue', value=12, uom='units')
#
#     Note: This does not work if a fragment is actually a field, not a
#     structure own its own. A direct assignment to such a value fragment,
#     like
#
#         mo.c8y_CustomReferences = [1, 2, 3]
#
#     is currently not supported nicely as it will not be recognised as an
#     update. A manual update flagging is required:
#
#         mo.c8y_CustomReferences = [1, 2, 3]
#         mo.flag_update('c8y_CustomReferences')
#
#     See also https://cumulocity.com/guides/reference/inventory/#managed-object
#     """
#
#     _c8y_api = "Inventory"
#
#     def __init__(
#             self,
#             c8y: CumulocityRestApi = None,
# type: str = None,
#             name: str = None,
#             owner: str = None,
#             **kwargs
#     ):
#         """ Create a new ManagedObject instance.
#
#         Custom fragments can be added to the object using `kwargs` or after
#         creation using += or [] syntax.
#
#         Args:
#             c8y (CumulocityRestApi):  Cumulocity connection reference; needs
#                 to be set for direct manipulation (create, delete)
#             type (str):  ManagedObject type
#             name (str):  ManagedObject name
#             owner (str):  User ID of the owning user (can be left None to
#                 automatically assign to the connection user upon creation)
#             kwargs:  Additional arguments are treated as custom fragments
#
#         Returns:
#             ManagedObject instance
#         """
#         super().__init__(c8y, **kwargs)
#         self.type = type
#         self.name = name
#         self.owner = owner
#
#     type = json_property("type")
#     name = json_property("name")
#     owner = json_property("owner")
#
#     is_device = tag_property("c8y_IsDevice")
#     is_device_group = tag_property("c8y_IsDeviceGroup")
#     is_binary = tag_property("c8y_IsBinary")
#
#     creation_time = time_property("creationTime", read_only=True)
#     creation_datetime = datetime_property("creationTime")
#     update_time = time_property("updateTime", read_only=True)
#     update_datetime = datetime_property("updateTime")
#
#     child_devices = references_property("childDevices")
#     child_assets = references_property("childAssets")
#     child_additions = references_property("childAdditions")
#     parent_devices = references_property("deviceParents")
#     parent_assets = references_property("assetParents")
#     parent_additions = references_property("additionParents")
#
#     # def __repr__(self):
#     #     return self._repr('name', 'type')
#     #
#     async def reload(self) -> Self:
#         """Reload this object's data from database.
#
#         Returns:
#             New instance built from latest data.
#         """
#         assert_c8y(self)
#         assert_id(self)
#         return type(self)._build(
#             json=await self.c8y.get(Inventory.build_object_path(self.id)),
#             c8y=self.c8y,
#         )
#
#     async def create(self) -> Self:
#         """ Create a new representation of this object within the database.
#
#         This function can be called multiple times to create multiple
#         instances of this object with different ID.
#
#         Returns:
#             A fresh ManagedObject instance representing the created
#             object within the database. This instance can be used to get
#             at the ID of the new managed object.
#
#         See also function Inventory.create which doesn't parse the result.
#         """
#         return await self._create()
#
#     async def update(self) -> ManagedObject:
#         """ Write changes to the database.
#
#         Returns:
#             A fresh ManagedObject instance representing the updated
#             object within the database.
#
#         See also function Inventory.update which doesn't parse the result.
#         """
#         return await self._update()
#
#     async def apply_to(self, other_id: str) -> ManagedObject:
#         """Apply the details of this object to another object in the database.
#
#         Note: This will take the full details, not just the updates.
#
#         Args:
#             other_id (str):  Database ID of the event to update.
#         Returns:
#             A fresh ManagedObject instance representing the updated
#             object within the database.
#
#         See also function Inventory.apply_to which doesn't parse the result.
#         """
#         return await self._apply_to(other_id)
#
#     async def delete(self, **_) -> None:
#         """ Delete this object within the database.
#
#         Note: child additions, assets (and devices) are not implicitly
#         deleted. The database ID must be defined for this to function.
#
#         See also function Inventory.delete to delete multiple objects.
#         """
#         await self._delete()
#
#     async def delete_tree(self) -> None:
#         """Delete this managed object within the database including child.
#         additions, devices and assets.
#         This is equivalent to using the `forceCascade` parameter of the
#         Cumulocity REST API.
#
#         The database ID must be defined for this to function.
#
#         See also function DeviceInventory.delete_trees to delete multiple objects.
#         """
#         await self._delete(forceCascade='true')
#
#     async def assign_child_asset(self, child: ManagedObject | str):
#         """ Link a child asset to this managed object.
#
#         This operation is executed immediately. No additional call to
#         the `update` method is required.
#
#         Args:
#             child (ManagedObject|str): Child asset or its object ID
#         """
#         await self._assign_child("childAssets", child)
#
#     # todo: kick out or not?
#     add_child_asset = assign_child_asset
#     add_child_asset.__doc__ = assign_child_asset.__doc__
#
#     async def assign_child_device(self, child: ManagedObject | str):
#         """ Link a child device to this managed object.
#
#         This operation is executed immediately. No additional call to
#         the `update` method is required.
#
#         Args:
#             child (ManagedObject|str): Child device or its object ID
#         """
#         await self._assign_child("childDevices", child)
#
#     async def assign_child_addition(self, child: ManagedObject | str):
#         """ Link a child addition to this managed object.
#
#         This operation is executed immediately. No additional call to
#         the `update` method is required.
#
#         Args:
#             child (ManagedObject|str): Child addition or its object ID
#         """
#         await self._assign_child("childAdditions", child)
#
#     async def unassign_child_asset(self, child: ManagedObject | str):
#         """Remove the link to a child asset.
#
#         This operation is executed immediately. No additional call to
#         the `update` method is required.
#
#         Args:
#             child (ManagedObject|str): Child device or its object ID
#         """
#         await self._unassign_child("childAssets", child)
#
#     async def unassign_child_device(self, child: Device | str):
#         """Remove the link to a child device.
#
#         This operation is executed immediately. No additional call to
#         the `update` method is required.
#
#         Args:
#             child (Device|str): Child device or its object ID
#         """
#         await self._unassign_child("childDevices", child)
#
#     async def unassign_child_addition(self, child: ManagedObject | str):
#         """Remove the link to a child addition.
#
#         This operation is executed immediately. No additional call to
#         the `update` method is required.
#
#         Args:
#             child (ManagedObject|str): Child device or its object ID
#         """
#         await self._unassign_child("childAdditions", child)
#
#     async def _assign_child(self, resource, child: ManagedObject | str):
#         assert_c8y(self)
#         assert_id(self)
#         child_id = child.id if hasattr(child, "id") else child
#         await self.c8y.post(f"{self.object_path}/{resource}", json=ObjectReference.to_json(child_id), accept=None)
#
#     async def _unassign_child(self, resource, child: ManagedObject | str):
#         assert_c8y(self)
#         assert_id(self)
#         child_id = child.id if hasattr(child, "id") else child
#         await self.c8y.delete(f"{self.object_path}/{resource}/{child_id}")
#
#     async def _get_resource(self, resource) -> dict | list:
#         """Retrieve a sub resource for this managed object.
#
#         This will automatically unwrap the JSON's top-level element if there is any.
#         """
#         assert_c8y(self)
#         assert_id(self)
#         result_json = await self.c8y.get(f"{self.object_path}/{resource}")
#         if len(result_json) == 1:
#             return next(iter(result_json.values()))
#         return result_json
#
#     async def get_latest_availability(self) -> Availability:
#         """Retrieve the latest availability information of this object.
#
#         Return:
#             DeviceAvailability object
#         """
#         return Availability(await self._get_resource("availability"))
#
#     async def get_supported_measurements(self) -> list[str]:
#         """Retrieve all supported measurement names of this managed object.
#
#         Return:
#             List of measurement fragment names.
#         """
#         return await self._get_resource("supportedMeasurements")
#
#     async def get_supported_series(self) -> list[str]:
#         """Retrieve all supported measurement series names of this managed object.
#
#         Return:
#             List of measurement series names.
#         """
#         return await self._get_resource("supportedSeries")
#
#
#
# class OtherDevice(ManagedObject):
#     """ Represent an instance of a Device object within Cumulocity.
#
#     Instances of this class are returned by functions of the corresponding
#     DeviceInventory API. Use this class to create new or update Device
#     objects.
#
#     Device objects are regular managed objects with additional standardized
#     fragments and fields.
#
#     See also https://cumulocity.com/guides/reference/inventory/#managed-object
#         https://cumulocity.com/guides/reference/device-management/
#     """
#
#     def __init__(self, c8y: CumulocityRestApi = None,
# type: # str = None, name: str = None, owner: str = None, **kwargs):
#         """ Create a new Device instance.
#
#         A Device object will always have a `c8y_IsDevice` fragment.
#         Additional custom fragments can be added using `kwargs` or
#         after creation, using += or [] syntax.
#
#         Args:
#             c8y (CumulocityRestApi):  Cumulocity connection reference; needs
#                 to be set for direct manipulation (create, delete)
#             type (str):  Device type
#             name (str):  Device name
#             owner (str):  User ID of the owning user (can be left None to
#                 automatically assign to the connection user upon creation)
#             kwargs:  Additional arguments are treated as custom fragments
#
#         Returns:
#             Device instance
#         """
#         super().__init__(c8y=c8y, type=type, name=name, owner=owner, **kwargs)
#         self.__update_json["c8y_IsDevice"] = {}
#
#     def get_username(self) -> str:
#         """Return the device username.
#
#         Returns:
#             Username of the device's user.
#         """
#         assert self.name, "Device name must be defined."
#         return f"device_{self.name}"
#
#     # def get_user(self) -> User:  TODO: fix
#     #     """Return the device user.
#     #
#     #     Returns:
#     #         Device's user.
#     #     """
#     #     return Users(self.c8y).get(self.get_username())
#
#     async def delete(self, with_device_user=False, **_) -> None:
#         """Delete this device object within the database.
#
#         Note: child additions, assets (and devices) are not implicitly
#         deleted. The database ID must be defined for this to function.
#
#         Args:
#             with_device_user (bool):  Whether the device user is deleted
#                 as well.
#
#         See also function DeviceInventory.delete to delete multiple objects.
#         """
#         if with_device_user:
#             await self._delete(withDeviceUser='true')
#         else:
#             await self._delete()
#
#     async def delete_tree(self, with_device_user=False) -> None:
#         """Delete this device object within the database including child.
#         additions, devices and assets.
#
#         The database ID must be defined for this to function.
#
#         Args:
#             with_device_user (bool):  Whether the device user is deleted
#                 as well.
#
#         See also function DeviceInventory.delete to delete multiple objects.
#         """
#         if with_device_user:
#             await self._delete(cascade='true', withDeviceUser='true')
#         else:
#             await self._delete(cascade='true')
#
#
#
# class OtherDeviceGroup(ManagedObject):
#     """ Represent a device group within Cumulocity.
#
#     Instances of this class are returned by functions of the corresponding
#     DeviceGroupInventory API. Use this class to create new or update
#     DeviceGroup objects.
#
#     DeviceGroup objects are regular managed objects with additional
#     standardized fragments and fields.
#
#     See also https://cumulocity.com/guides/reference/inventory/#managed-object
#         https://cumulocity.com/guides/users-guide/device-management/#grouping-devices
#     """
#
#     ROOT_TYPE = 'c8y_DeviceGroup'
#     CHILD_TYPE = 'c8y_DeviceSubGroup'
#
#     def __init__(self, c8y=None, root: bool = False, name: str = None, owner: str = None, **kwargs):
#         """ Build a new DeviceGroup object.
#
#         The `type` of a device group will always be either `c8y_DeviceGroup`
#         or `c8y_DeviceSubGroup` (depending on it's level). This is handled
#         by the API.
#
#         A DeviceGroup object will always have a `c8y_IsDeviceGroup` fragment.
#         Additional custom fragments can be added using `kwargs` or after
#         creation, using += or [] syntax.
#
#         Args:
#             c8y (CumulocityRestApi):  Cumulocity connection reference; needs
#                 to be set for direct manipulation (create, delete)
#             root (bool):  Whether the group is a root group (default is False)
#             name (str):  Device name
#             owner (str):  User ID of the owning user (can be left None to
#                 automatically assign to the connection user upon creation)
#             kwargs:  Additional arguments are treated as custom fragments
#
#         Returns:
#             DeviceGroup instance
#         """
#         super().__init__(c8y=c8y, type=self.ROOT_TYPE if root else self.CHILD_TYPE,
#                          name=name, owner=owner, **kwargs)
#         self._update_json["c8Y_IsDeviceGroup"] = {}
#
#     async def create_child(self, name: str, owner: str = None, **kwargs) -> DeviceGroup:
#         """ Create and assign a child group.
#
#         This change is written to the database immediately.
#
#         Args:
#             name (str):  Device name
#             owner (str):  User ID of the owning user (can be left None to
#                 automatically assign to the connection user upon creation)
#             kwargs:  Additional arguments are treated as custom fragments
#
#         Returns:
#             The newly created DeviceGroup object
#         """
#         assert_id(self)
#         assert_c8y(self)
#         child = await DeviceGroup(c8y=self.c8y, name=name, owner=owner if owner else self.owner, **kwargs).create()
#         await self.assign_child_asset(child.id)
#         return child
#
#     async def create(self) -> DeviceGroup:
#         """ Create a new representation of this object within the database.
#
#         This operation will create the group and all added child groups
#         within the database.
#
#         :returns:  A fresh DeviceGroup instance representing the created
#             object within the database. This instance can be used to get at
#             the ID of the new object.
#
#         See also function DeviceGroupInventory.create which doesn't parse
#         the result.
#         """
#         return await self._create()
#
#     async def update(self) -> DeviceGroup:
#         """ Write changed to the database.
#
#         Note: Removing child groups is currently not supported.
#
#         :returns:  A fresh DeviceGroup instance representing the updated
#             object within the database.
#         """
#         return await self._update()
#
#     def delete(self, **_) -> None:
#         """Delete this device group.
#
#         The child groups (if there are any) are left dangling. This is
#         equivalent to using the `cascade=false` parameter in the
#         Cumulocity REST API.
#         """
#         self._delete(cascade='false')
#
#     def delete_tree(self) -> None:
#         """Delete this device group and its children.
#
#         This is equivalent to using the `cascade=true` parameter in the
#         Cumulocity REST API.
#         """
#         self._delete(cascade='true')
#
#     def assign_child_group(self, child: DeviceGroup | str):
#         """Link a child group to this device group.
#
#         This operation is executed immediately. No additional call to
#         the `update` method is required.
#
#         Args:
#             child (DeviceGroup|str): Child device or its object ID
#         """
#         self.assign_child_asset(child)
#
#     def unassign_child_group(self, child: DeviceGroup | str):
#         """Remove the link to a child group.
#
#         This operation is executed immediately. No additional call to
#         the `update` method is required.
#
#         Args:
#             child (DeviceGroup|str): Child device or its object ID
#         """
#         self.unassign_child_asset(child)
#

MO = TypeVar("MO", bound="ManagedObject")


class Inventory(CumulocityResource[MO]):
    _meta = InventoryMeta
    _object_type = ManagedObject
    _only_devices = False

    async def get(
        self,
        id: str,  # noqa
        *,
        with_children: bool = None,
        with_children_count: bool = None,
        skip_children_names: bool = None,
        with_parents: bool = None,
        with_latest_values: bool = None,
        **kwargs,
    ) -> MO:
        """Retrieve a specific managed object from the database.

        Args:
            id (str): Cumulocity ID of the managed object
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
             A ManagedObject instance

        Raises:
            KeyError:  if the ID is not defined within the database
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
        expression: str = None,
        *,
        query: str = None,
        ids: list[str] = None,
        order_by: str = None,
        type: str = None,
        parent: str = None,
        fragment: str = None,
        fragments: list[str] = None,
        name: str = None,
        owner: str = None,
        text: str = None,
        only_roots: bool = None,
        with_children: bool = None,
        with_children_count: bool = None,
        skip_children_names: bool = None,
        with_groups: bool = None,
        with_parents: bool = None,
        with_latest_values: bool = None,
        as_values: AsValuesSpec | None = None,
        **kwargs,
    ) -> MO | Any | tuple[Any]:
        """Query the database for a specific managed object.

        This function is a special version of the `select` function assuming a single
        result being returned by the query.

        Returns:
            A ManagedObject instance

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
        expression: str = None,
        *,
        query: str = None,
        ids: str | Sequence[str] = None,
        type: str = None,
        parent: str = None,
        fragment: str = None,
        fragments: Sequence[str] = None,
        name: str = None,
        owner: str = None,
        text: str = None,
        **kwargs,
    ) -> int:
        """Calculate the number of potential results of a database query.

        This function uses the same parameters as the `select` function.

        Returns:
            Number of potential results
        """
        params = (
            map_params(
                **self._collate_filter_params(
                    only_devices=self._only_devices,
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
        expression: str = None,
        *,
        query: str = None,
        ids: list[str] = None,
        order_by: str = None,
        type: str = None,
        parent: str = None,
        fragment: str = None,
        fragments: list[str] = None,
        name: str = None,
        owner: str = None,
        text: str = None,
        only_roots: bool = None,
        with_children: bool = None,
        with_children_count: bool = None,
        skip_children_names: bool = None,
        with_groups: bool = None,
        with_parents: bool = None,
        with_latest_values: bool = None,
        limit: int = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        page_size: int = 1000,
        page_number: int = None,
        as_values: AsValuesSpec | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[MO | Any | tuple[Any]]:
        """Query the database for managed objects and return the results
        as list.

        This function is a greedy version of the `select` function. All
        available results are read immediately and returned as list.

        Returns:
            List of ManagedObject instances or values/value tuples if
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
        expression: str = None,
        *,
        query: str = None,
        ids: list[str] = None,
        order_by: str = None,
        type: str = None,
        parent: str = None,
        fragment: str = None,
        fragments: list[str] = None,
        name: str = None,
        owner: str = None,
        text: str = None,
        only_roots: bool = None,
        with_children: bool = None,
        with_children_count: bool = None,
        skip_children_names: bool = None,
        with_groups: bool = None,
        with_parents: bool = None,
        with_latest_values: bool = None,
        limit: int = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        page_size: int = 1000,
        page_number: int = None,
        as_values: AsValuesSpec | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[MO | Any | tuple[Any]]:
        """Query the database for managed objects and iterate over the
        results.

        This function is implemented in a lazy fashion - results will only be
        fetched from the database as long there is a consumer for them.

        All parameters are considered to be filters, limiting the result set
        to objects which meet the filters specification.  Filters can be
        combined (within reason).

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            limit (int): Limit the number of results to this number.
            include (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The inclusion is applied first.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            exclude (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The exclusion is applied second.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            page_size (int): Define the number of events which are read (and
                parsed in one chunk). This is a performance related setting.
            page_number (int): Pull a specific page; this effectively disables
                automatic follow-up page retrieval.
            as_values: (*str|tuple):  Don't parse objects, but directly extract
                the values at certain JSON paths as tuples; If the path is not
                defined in a result, None is used; Specify a tuple to define
                a proper default value for each path.

        Returns:
            Async iterator for ManagedObject instances or values/value
                tuples if the `as_values` parameter is defined.

        See also:
            https://github.com/bytebutcher/pydfql/blob/main/docs/USER_GUIDE.md#4-query-language
        """
        return self._select(
            device_mode=self._only_devices,
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
            page_size=sanitize_page_size(limit, page_size),
            page_number=page_number,
            as_values=as_values,
            workers=workers,
            **kwargs,
        )

    async def get_latest_availability(self, mo_id: str) -> Availability:
        """Retrieve the latest availability information of a managed object.

        Args:
            mo_id (str):  Device (managed object) ID

        Return:
            DeviceAvailability object
        """
        return Availability(await self.c8y.get(f"{self.build_object_path(mo_id)}/availability"))

    async def get_supported_measurements(self, mo_id: str) -> [str]:
        """Retrieve all supported measurements names of a specific managed
        object.

        Args:
            mo_id (str):  Managed object ID

        Return:
            List of measurement fragment names.
        """
        result_json = await self.c8y.get(f"{self.build_object_path(mo_id)}/supportedMeasurements")
        return result_json["c8y_SupportedMeasurements"]

    async def get_supported_series(self, mo_id: str) -> [str]:
        """Retrieve all supported measurement series names of a specific
        managed object.

        Args:
            mo_id (str):  Managed object ID

        Return:
            List of series names.
        """
        result_json = await self.c8y.get(f"{self.build_object_path(mo_id)}/supportedSeries")
        return result_json["c8y_SupportedSeries"]

    async def create(self, *objects: MO, workers: int | None) -> None:
        return await self._create(*objects, workers=workers)

    async def update(self, *objects: MO, workers: int | None) -> None:
        return await self._update(*objects, workers=workers)

    async def apply_to(self, model: dict | MO, *objects: str | MO, workers: int | None = None) -> None:
        return await self._apply_to(model, *objects, workers=workers)

    async def delete(self, *objects: str | MO, workers: int | None = None) -> None:
        return await self._delete(*objects, workers=workers)

    def _select(
        self,
        device_mode: bool,
        expression: str = None,
        query: str = None,
        ids: list[str] = None,
        order_by: str = None,
        type: str = None,
        parent: str = None,
        fragment: str = None,
        fragments: str | list[str] = None,
        name: str = None,
        owner: str = None,
        text: str = None,
        limit: int = None,
        page_number: int = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        as_values: AsValuesSpec | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[MO | Any | tuple[Any]]:
        """Generic select function to be used by derived classes as well."""
        params = (
            map_params(
                **self._collate_filter_params(
                    only_devices=device_mode,
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
        return super()._iterate(
            expression=expression,
            params=params,
            page_number=page_number,
            limit=limit,
            include=include,
            exclude=exclude,
            as_values=as_values,
            workers=workers,
        )

    @staticmethod
    def _collate_filter_params(
        only_devices: bool,
        query: str = None,
        ids: list[str] = None,
        filters: list[str] = None,
        order_by: str = None,
        type: str = None,
        parent: str = None,
        fragment: str = None,
        fragments: list[str] = None,
        name: str = None,
        owner: str = None,
        text: str = None,
        **kwargs,
    ) -> dict:
        """Collate the various different filtering options."""
        query_key = "q" if only_devices else "query"

        # if query is directly specified -> use it and ignore everything else
        if query:
            return {query_key: query, **kwargs}
        # if ids are directly specified -> use it and ignore everything else
        if ids:
            return {"ids": ids, **kwargs}

        def filter_none(**xs):
            return {k: v for k, v in xs.items() if v is not None}

        if only_devices:
            if fragments:
                fragments = ["c8y_IsDevice", *fragments]
            elif fragment:
                fragments = ["c8y_IsDevice", fragment]
            else:
                fragment = "c8y_IsDevice"
        use_query = parent or filters or order_by or name or fragments
        if not use_query:
            return filter_none(type=type, owner=owner, text=text, fragment=fragment, **kwargs)

        # if any of the given filter is 'special' we have to convert to a query
        filters = filters or []

        # add fragment filters
        fragments = fragments or ([fragment] if fragment else [])
        if fragments:
            filters.extend([f"has({x})" for x in fragments])
        if parent:
            filters.append(f"bygroupid({parent})")
        if name:
            filters.append(f"name eq '{encode_odata_query_value(name)}'")
        if type:
            filters.append(f"type eq {type}")
        if owner:
            filters.append(f"owner eq {owner}")
        if text:
            filters.append(f"text eq '{encode_odata_query_value(text)}'")

        # convert to single query parameter
        order_by = f"+$orderby={order_by}" if order_by else ""
        query = f'$filter=({" and ".join(filters)}){order_by}'

        return {query_key: query, **kwargs}


class DeviceInventory(Inventory[Device]):
    """Provides access to the Device Inventory API.

    This class can be used for get, search for, create, update and
    delete device objects within the Cumulocity database.

    See also: https://cumulocity.com/api/#tag/Inventory-API
    """

    _only_devices = True

    async def request(self, id: str):  # noqa (id)
        """Create a device request.

        Args:
            id (str): Unique ID of the device (e.g. Serial, IMEI); this is
            _not_ the database ID.
        """
        await self.c8y.post("/devicecontrol/newDeviceRequests", {"id": id})

    async def accept(self, id: str):  # noqa (id)
        """Accept a device request.

        Args:
            id (str): Unique ID of the device (e.g. Serial, IMEI); this is
            _not_ the database ID.
        """
        await self.c8y.put("/devicecontrol/newDeviceRequests/" + str(id), {"status": "ACCEPTED"})

    async def delete(self, workers: int = None, *devices: Device) -> None:
        """Delete one or more devices and the corresponding within the database.

        The objects can be specified as instances of a database object
        (then, the id field needs to be defined) or simply as ID (integers
        or strings).

        Note: In contrast to the regular `delete` function defined in class
        ManagedObject, this version also removes the corresponding device
        user from database by invoking the `delete` function on the `Device`
        object which does this by default.

        Args:
            workers (int): Number of workers to use for parallel processing
                or None to process sequentially.
           *devices (Device): Device objects within the database specified
                (with defined ID).
        """
        devices = flatten(devices)
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
        expression: str = None,
        *,
        query: str = None,
        ids: list[str] = None,
        parent: str = None,
        type: str = None,
        fragment: str = None,
        fragments: list[str] = None,
        name: str = None,
        owner: str = None,
        text: str = None,
        **kwargs,
    ) -> int:
        # pylint: disable=arguments-differ, arguments-renamed
        type = type or (DeviceGroup.CHILD_TYPE if parent else None)
        if fragments:
            fragments = ["c8y_IsDeviceGroup", *fragments]
        elif fragment:
            fragments = ["c8y_IsDeviceGroup", fragment]
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
        expression: str = None,
        *,
        query: str = None,
        ids: Sequence[str] = None,
        order_by: str = None,
        type: str = None,
        parent: str = None,
        fragment: str = None,
        fragments: Sequence[str] = None,
        name: str = None,
        owner: str = None,
        text: str = None,
        only_roots: bool = None,
        with_children: bool = None,
        with_children_count: bool = None,
        skip_children_names: bool = None,
        with_groups: bool = None,
        with_parents: bool = None,
        with_latest_values: bool = None,
        limit: int = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        page_size: int = 100,
        page_number: int = None,
        as_values: AsValuesSpec | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[DeviceGroup | Any | tuple[Any]]:
        # pylint: disable=arguments-differ, arguments-renamed
        type = type or (DeviceGroup.CHILD_TYPE if parent else None)
        if fragments:
            fragments = ["c8y_IsDeviceGroup", *fragments]
        elif fragment:
            fragments = ["c8y_IsDeviceGroup", fragment]
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
            page_size=sanitize_page_size(limit, page_size),
            page_number=page_number,
            as_values=as_values,
            workers=workers,
            **kwargs,
        )


def update_doc(doc, object_type, object_name):
    return doc.replace("ManagedObject", object_type).replace("managed object", object_name)


as_device_doc = lambda doc: update_doc(doc, "Device", "device")

DeviceInventory.get.__doc__ = as_device_doc(Inventory.get.__doc__)
DeviceInventory.get_by.__doc__ = as_device_doc(Inventory.get_by.__doc__)
DeviceInventory.get_all.__doc__ = as_device_doc(Inventory.get_all.__doc__)
DeviceInventory.select.__doc__ = as_device_doc(Inventory.select.__doc__)
