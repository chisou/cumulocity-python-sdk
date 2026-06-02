# Copyright (c) 2026 Christoph Souris

from dataclasses import dataclass
from typing import Self, Any

from pyc8y.model.user import User, Users
from pyc8y.rest import CumulocityRestClient
from pyc8y.model.model_base import (
    CumulocityObject,
    JsonObject,
    WithId,
    json_property,
    time_property,
    datetime_property,
    tag_property,
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
    # TODO: Other references than managed objects?
    def getter(self):
        return [
            ObjectReference(x["managedObject"]["id"], x["managedObject"].get("name", None))
            for x in self._source_json[key]["references"]
        ]

    return property(getter)


class Availability(JsonObject):
    """Cumulocity availability status labels"""

    class ConnectionStatus:
        """Connection status labels"""

        CONNECTED = "CONNECTED"
        DISCONNECTED = "DISCONNECTED"

    class DataStatus:
        """Data status labels"""

        AVAILABLE = "AVAILABLE"
        UNAVAILABLE = "UNAVAILABLE"

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


class ManagedObject(WithId, CumulocityObject):
    """Represent a managed object within the database.

    Instances of this class are returned by functions of the corresponding
    Inventory API. Use this class to create new or update managed objects.

    See also https://cumulocity.com/guides/reference/inventory/#managed-object
    """

    _meta = InventoryMeta

    def __init__(
        self, c8y: CumulocityRestClient | None = None, type: str | None = None, name: str | None = None, owner: str | None = None, **kwargs
    ):
        """Create a new ManagedObject instance.

        Custom fragments can be added to the object using `kwargs` or after
        creation using += or [] syntax.

        Args:
            c8y (CumulocityRestClient):  Cumulocity connection reference; needs
                to be set for direct manipulation (create, delete)
            type (str):  ManagedObject type
            name (str):  ManagedObject name
            owner (str):  User ID of the owning user (can be left None to
                automatically assign to the connection user upon creation)
            kwargs:  Additional arguments are treated as custom fragments

        Returns:
            ManagedObject instance
        """
        super().__init__(c8y, **kwargs)
        self.type = type
        self.name = name
        self.owner = owner

    type = json_property("type")
    name = json_property("name")
    owner = json_property("owner")

    is_device = tag_property("c8y_IsDevice")
    is_device_group = tag_property("c8y_IsDeviceGroup")
    is_binary = tag_property("c8y_IsBinary")

    creation_time = time_property("creationTime", read_only=True)
    creation_datetime = datetime_property("creationTime")
    update_time = time_property("updateTime", read_only=True)
    update_datetime = datetime_property("updateTime")

    child_devices = references_property("childDevices")
    child_assets = references_property("childAssets")
    child_additions = references_property("childAdditions")
    parent_devices = references_property("deviceParents")
    parent_assets = references_property("assetParents")
    parent_additions = references_property("additionParents")

    async def reload(self, copy: bool = False) -> Self:
        """Reload this object's data from database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The reloaded ManagedObject. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._reload(copy)

    async def create(self) -> Self:
        """Create a new representation of this object within the database.

        This function can be called multiple times to create multiple
        instances of this object with different ID.

        Returns:
            A fresh ManagedObject instance representing the created
            object within the database. This instance can be used to get
            at the ID of the new managed object.

        See also function Inventory.create which doesn't parse the result.
        """
        return await self._create()

    async def update(self, copy: bool = False) -> Self:
        """Write changes to the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated ManagedObject. By default this is `self`; if `copy=True`,
            a fresh instance.

        See also function Inventory.update which doesn't parse the result.
        """
        return await self._update(copy)

    async def apply(self, json: dict, copy: bool = False) -> Self:
        """Apply a JSON model to this object.

        Args:
            json (dict):  A JSON document to apply
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated ManagedObject. By default, this is `self`; if `copy=True`,
            a fresh instance.

        """
        return await self._apply(json, copy)

    async def apply_to(self, other_id: str) -> Self:
        """Apply the details of this object to another object in the database.

        Note: This will take the full details, not just the updates.

        Args:
            other_id (str):  Database ID of the event to update.
        Returns:
            A fresh ManagedObject instance representing the updated
            object within the database.

        See also function Inventory.apply_to which doesn't parse the result.
        """
        return await self._apply_to(other_id)

    async def delete(self, **_) -> None:
        """Delete this object within the database.

        Note: child additions, assets (and devices) are not implicitly
        deleted. The database ID must be defined for this to function.

        See also function Inventory.delete to delete multiple objects.
        """
        await self._delete()

    async def delete_tree(self) -> None:
        """Delete this managed object within the database including child.
        additions, devices and assets.
        This is equivalent to using the `forceCascade` parameter of the
        Cumulocity REST API.

        The database ID must be defined for this to function.

        See also function DeviceInventory.delete_trees to delete multiple objects.
        """
        await self._delete(forceCascade="true")

    async def assign_child_asset(self, child: Self | str):
        """Link a child asset to this managed object.

        This operation is executed immediately. No additional call to
        the `update` method is required.

        Args:
            child (ManagedObject|str): Child asset or its object ID
        """
        await self._assign_child("childAssets", child)

    # todo: kick out or not?
    add_child_asset = assign_child_asset
    add_child_asset.__doc__ = assign_child_asset.__doc__

    async def assign_child_device(self, child: Self | str):
        """Link a child device to this managed object.

        This operation is executed immediately. No additional call to
        the `update` method is required.

        Args:
            child (ManagedObject|str): Child device or its object ID
        """
        await self._assign_child("childDevices", child)

    # todo: kick out or not?
    add_child_device = assign_child_device
    add_child_device.__doc__ = assign_child_device.__doc__

    async def assign_child_addition(self, child: Self | str):
        """Link a child addition to this managed object.

        This operation is executed immediately. No additional call to
        the `update` method is required.

        Args:
            child (ManagedObject|str): Child addition or its object ID
        """
        await self._assign_child("childAdditions", child)

    # todo: kick out or not?
    add_child_addition = assign_child_addition
    add_child_addition.__doc__ = assign_child_addition.__doc__

    async def unassign_child_asset(self, child: Self | str):
        """Remove the link to a child asset.

        This operation is executed immediately. No additional call to
        the `update` method is required.

        Args:
            child (ManagedObject|str): Child device or its object ID
        """
        await self._unassign_child("childAssets", child)

    async def unassign_child_device(self, child: Self | str):
        """Remove the link to a child device.

        This operation is executed immediately. No additional call to
        the `update` method is required.

        Args:
            child (ManagedObject|str): Child device or its object ID
        """
        await self._unassign_child("childDevices", child)

    async def unassign_child_addition(self, child: Self | str):
        """Remove the link to a child addition.

        This operation is executed immediately. No additional call to
        the `update` method is required.

        Args:
            child (ManagedObject|str): Child device or its object ID
        """
        await self._unassign_child("childAdditions", child)

    async def _assign_child(self, resource, child: Self | str):
        self._assert_c8y()
        self._assert_key()
        child_id = child.id if hasattr(child, "id") else child
        await self.c8y.post(f"{self.object_path}/{resource}", json=ObjectReference.to_json(child_id), accept=None)

    async def _unassign_child(self, resource, child: Self | str):
        self._assert_c8y()
        self._assert_key()
        child_id = child.id if hasattr(child, "id") else child
        await self.c8y.delete(f"{self.object_path}/{resource}/{child_id}")

    async def _get_resource(self, resource) -> Any:
        """Retrieve a sub resource for this managed object.

        This will automatically unwrap the JSON's top-level element if there is any.
        """
        self._assert_c8y()
        self._assert_key()
        result_json = await self.c8y.get(f"{self.object_path}/{resource}")
        if len(result_json) == 1:
            return next(iter(result_json.values()))
        return result_json

    async def get_latest_availability(self) -> Availability:
        """Retrieve the latest availability information of this object.

        Return:
            DeviceAvailability object
        """
        return Availability(await self._get_resource("availability"))

    async def get_supported_measurements(self) -> list[str]:
        """Retrieve all supported measurement names of this managed object.

        Return:
            List of measurement fragment names.
        """
        return await self._get_resource("supportedMeasurements")

    async def get_supported_series(self) -> list[str]:
        """Retrieve all supported measurement series names of this managed object.

        Return:
            List of measurement series names.
        """
        return await self._get_resource("supportedSeries")


class Device(ManagedObject):
    """Represent an instance of a Device object within Cumulocity.

    Instances of this class are returned by functions of the corresponding
    DeviceInventory API. Use this class to create new or update Device
    objects.

    Device objects are regular managed objects with additional standardized
    fragments and fields.

    See also https://cumulocity.com/guides/reference/inventory/#managed-object
        https://cumulocity.com/guides/reference/device-management/
    """

    def __init__(
        self, c8y: CumulocityRestClient | None = None, type: str | None = None, name: str | None = None, owner: str | None = None, **kwargs
    ):  # noqa
        """Create a new Device instance.

        A Device object will always have a `c8y_IsDevice` fragment.
        Additional custom fragments can be added using `kwargs` or
        after creation, using += or [] syntax.

        Args:
            c8y (CumulocityRestClient):  Cumulocity connection reference; needs
                to be set for direct manipulation (create, delete)
            type (str):  Device type
            name (str):  Device name
            owner (str):  User ID of the owning user (can be left None to
                automatically assign to the connection user upon creation)
            kwargs:  Additional arguments are treated as custom fragments

        Returns:
            Device instance
        """
        super().__init__(c8y=c8y, type=type, name=name, owner=owner, **kwargs)
        self._staged_json["c8y_IsDevice"] = {}

    def get_username(self) -> str:
        """Return the device username.

        Returns:
            Username of the device's user.
        """
        assert self.name, "Device name must be defined."
        return f"device_{self.name}"

    async def get_user(self) -> User:
        """Return the device user.

        Returns:
            Device's user.
        """
        self._assert_c8y()
        return await Users(self.c8y).get(self.get_username())  # type: ignore (asserted)

    async def delete(self, with_device_user=False, **_) -> None:
        """Delete this device object within the database.

        Note: child additions, assets (and devices) are not implicitly
        deleted. The database ID must be defined for this to function.

        Args:
            with_device_user (bool):  Whether the device user is deleted
                as well.

        See also function DeviceInventory.delete to delete multiple objects.
        """
        if with_device_user:
            await self._delete(withDeviceUser="true")
        else:
            await self._delete()

    async def delete_tree(self, with_device_user=False) -> None:
        """Delete this device object within the database including child.
        additions, devices and assets.

        The database ID must be defined for this to function.

        Args:
            with_device_user (bool):  Whether the device user is deleted
                as well.

        See also function DeviceInventory.delete to delete multiple objects.
        """
        if with_device_user:
            await self._delete(cascade="true", withDeviceUser="true")
        else:
            await self._delete(cascade="true")


class DeviceGroup(ManagedObject):
    """Represent a device group within Cumulocity.

    Instances of this class are returned by functions of the corresponding
    DeviceGroupInventory API. Use this class to create new or update
    DeviceGroup objects.

    DeviceGroup objects are regular managed objects with additional
    standardized fragments and fields.

    See also https://cumulocity.com/guides/reference/inventory/#managed-object
        https://cumulocity.com/guides/users-guide/device-management/#grouping-devices
    """

    ROOT_TYPE = "c8y_DeviceGroup"  # TODO: -> types.py?
    CHILD_TYPE = "c8y_DeviceSubGroup"

    def __init__(self, c8y=None, root: bool = False, name: str | None = None, owner: str | None = None, **kwargs):
        """Build a new DeviceGroup object.

        The `type` of a device group will always be either `c8y_DeviceGroup`
        or `c8y_DeviceSubGroup` (depending on it's level). This is handled
        by the API.

        A DeviceGroup object will always have a `c8y_IsDeviceGroup` fragment.
        Additional custom fragments can be added using `kwargs` or after
        creation, using += or [] syntax.

        Args:
            c8y (CumulocityRestClient):  Cumulocity connection reference; needs
                to be set for direct manipulation (create, delete)
            root (bool):  Whether the group is a root group (default is False)
            name (str):  Device name
            owner (str):  User ID of the owning user (can be left None to
                automatically assign to the connection user upon creation)
            kwargs:  Additional arguments are treated as custom fragments

        Returns:
            DeviceGroup instance
        """
        super().__init__(c8y=c8y, type=self.ROOT_TYPE if root else self.CHILD_TYPE, name=name, owner=owner, **kwargs)
        self._staged_json["c8y_IsDeviceGroup"] = {}

    async def create_child(self, name: str, owner: str | None = None, **kwargs) -> Self:
        """Create and assign a child group.

        This change is written to the database immediately.

        Args:
            name (str):  Device name
            owner (str):  User ID of the owning user (can be left None to
                automatically assign to the connection user upon creation)
            kwargs:  Additional arguments are treated as custom fragments

        Returns:
            The newly created DeviceGroup object
        """
        self._assert_key()
        self._assert_c8y()
        child = await DeviceGroup(c8y=self.c8y, name=name, owner=owner if owner else self.owner, **kwargs).create()  # type: ignore (asserted)
        await self.assign_child_asset(child.id)
        return child

    async def create(self) -> Self:
        """Create a new representation of this object within the database.

        This operation will create the group and all added child groups
        within the database.

        :returns:  A fresh DeviceGroup instance representing the created
            object within the database. This instance can be used to get at
            the ID of the new object.

        See also function DeviceGroupInventory.create which doesn't parse
        the result.
        """
        return await self._create()

    async def update(self, copy: bool = False, **_) -> Self:
        """Write changed to the database.

        Note: Removing child groups is currently not supported.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        :returns:  The updated DeviceGroup. By default this is `self`; if
            `copy=True`, a fresh instance.
        """
        return await self._update(copy)

    async def delete(self, **_) -> None:
        """Delete this device group.

        The child groups (if there are any) are left dangling. This is
        equivalent to using the `cascade=false` parameter in the
        Cumulocity REST API.
        """
        await self._delete(cascade="false")

    async def delete_tree(self) -> None:
        """Delete this device group and its children.

        This is equivalent to using the `cascade=true` parameter in the
        Cumulocity REST API.
        """
        await self._delete(cascade="true")

    async def assign_child_group(self, child: Self | str):
        """Link a child group to this device group.

        This operation is executed immediately. No additional call to
        the `update` method is required.

        Args:
            child (DeviceGroup|str): Child device or its object ID
        """
        await self.assign_child_asset(child)

    async def unassign_child_group(self, child: Self | str):
        """Remove the link to a child group.

        This operation is executed immediately. No additional call to
        the `update` method is required.

        Args:
            child (DeviceGroup|str): Child device or its object ID
        """
        await self.unassign_child_asset(child)
