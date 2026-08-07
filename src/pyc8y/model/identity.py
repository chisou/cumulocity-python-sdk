# Copyright (c) 2026 Christoph Souris

from typing import Self

from pyc8y.rest import CumulocityRestClient
from pyc8y.model.inventory import Inventory
from pyc8y.model.model_base import CumulocityObject, json_property, id_property, CumulocityResource, run_batched
from pyc8y.types import IdentityMeta


def _build_resource_path(managed_object_id: str) -> str:
    return f"/identity/globalIds/{managed_object_id}/externalIds"


def _build_object_path(external_id: str, external_type: str) -> str:
    return f"identity/externalIds/{external_type}/{external_id}"


def _build_json(external_id: str, external_type: str) -> dict:
    return {
        "externalId": external_id,
        "type": external_type,
    }


class ExternalId(CumulocityObject):
    """Represents an ExternalID in Cumulocity.

    Instances of this class are returned by functions of the corresponding
    Identity API. Use this class to create or remove external IDs.

    See also: https://cumulocity.com/api/core/#tag/External-IDs
    """

    # ExternalId uses non-standard paths managed by the Identity class.
    # _meta is not used for standard CRUD; only to satisfy the base class.
    _meta = IdentityMeta

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        *,
        external_id: str | None = None,
        external_type: str | None = None,
        managed_object_id: str | None = None,
    ):
        super().__init__(c8y)
        self.external_id = external_id
        self.external_type = external_type
        self.managed_object_id = managed_object_id

    external_id = json_property("externalId")
    external_type = json_property("type")
    managed_object_id = id_property("managedObject")

    @property
    def object_path(self) -> str:
        assert self.external_id is not None
        assert self.external_type is not None
        return _build_object_path(self.external_id, self.external_type)

    def _assert_key(self):
        if not self.external_id or not self.external_type:
            raise ValueError("Both external_id and external_type must be set to allow direct object access.")

    async def create(self, copy: bool = False) -> Self:
        """Store the external ID in the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The created ExternalId. By default, this is `self`; if `copy=True`,
            a fresh instance.
        """
        # can't use _create as object paths are built differently
        result_json = await self.c8y.post(
            _build_resource_path(self.managed_object_id),
            json=_build_json(self.external_id, self.external_type),
            content_type="application/vnd.com.nsn.cumulocity.externalid+json",
            accept="application/vnd.com.nsn.cumulocity.externalid+json",
        )
        if copy:
            return self._build(result_json, c8y=self.c8y)
        self._source_json = result_json
        return self

    async def delete(self) -> None:
        """Remove the external ID from the database."""
        # can't use _delete function as object IDs are built differently
        await self.c8y.delete(self.object_path)

    async def get_object(self):
        """Read the referenced managed object from the database.

        Returns:
            ManagedObject instance
        """
        return await Inventory(self.c8y).get(self.managed_object_id)


class Identity(CumulocityResource):
    """Provides access to the Identity API.

    The Identity API uses non-standard resource paths and does not follow
    the standard CumulocityResource pagination pattern.

    See also: https://cumulocity.com/api/core/#tag/External-IDs and https://cumulocity.com/api/core/#tag/Identity-API
    """

    _meta = IdentityMeta
    _object_type: ExternalId

    def __init__(self, c8y: CumulocityRestClient):
        super().__init__(c8y)

    async def create(
        self,
        *objects: ExternalId,
        workers: int | None = None,
        external_id: str | None = None,
        external_type: str | None = None,
        managed_object_id: str | None = None,
    ) -> None:
        """Create ExternalID objects within the database.

        A single ExternalID object can be created by specifying parameters
        `external_id`, `external_type`, and `managed_object_id` directly.
        Alternatively, a collection of ExternalID objects can be created
        in a single call, optionally specifying the number of parallel
        worker threads.

        Args:
            *objects (ExternalID): Collection of ExternalID instances
            workers (int): The number of parallel processes to use
            external_id (str):  A string to be used as ID for external use
            external_type (str):  Type of the external ID
            managed_object_id (str):  Valid database ID of a managed object
        """
        if objects:
            # standard _create function doesn't work because of how object paths are being built
            await run_batched(
                objects,
                workers,
                lambda x: self.c8y.post(
                    resource=_build_resource_path(x.managed_object_id),
                    json=_build_json(x.external_id, x.external_type),
                    accept=None,
                ),
            )
        else:
            # try to create a single external ID
            # TODO: ValueError if part is missing?
            await ExternalId(
                self.c8y, external_id=external_id, external_type=external_type, managed_object_id=managed_object_id
            ).create()

    async def delete(
        self,
        *objects: ExternalId,
        workers: int | None = None,
        external_id: str | None = None,
        external_type: str | None = None,
    ) -> None:
        """Remove an External ID from the database.

        A single ExternalID object can be deleted by specifying parameters
        `external_id` and `external_type` directly.
        Alternatively, a collection of ExternalID objects can be deleted
        in a single call, optionally specifying the number of parallel
        worker threads.

        Args:
            *objects (ExternalID): Collection of ExternalID instances
            workers (int): The number of parallel processes to use
            external_id (str):  A string to be used as ID for external use
            external_type (str):  Type of the external ID
        """
        if objects:
            # standard _delete function doesn't work because of how object paths are being built
            await run_batched(
                objects,
                workers,
                lambda x: self.c8y.delete(_build_object_path(x.external_id, x.external_type)),
            )
        else:
            await ExternalId(
                self.c8y,
                external_id=external_id,
                external_type=external_type,
            ).delete()

    async def get(self, external_id: str, external_type: str) -> ExternalId:
        """Obtain a specific External ID from the database.

        Args:
            external_id (str):  A string to be used as ID for external use
            external_type (str):  Type of the external ID

        Returns:
            ExternalId object
        """
        json = await self.c8y.get(_build_object_path(external_id, external_type))
        return ExternalId.from_json(json, c8y=self.c8y)

    async def get_id(self, external_id: str, external_type: str) -> str:
        """Read the ID of the referenced managed object by its external ID.

        Args:
            external_id (str):  A string to be used as ID for external use
            external_type (str):  Type of the external ID

        Returns:
            A database ID (string)
        """
        json = await self.c8y.get(_build_object_path(external_id, external_type))
        return json["managedObject"]["id"]

    async def get_object(self, external_id: str, external_type: str):
        """Read a managed object by its external ID reference.

        Args:
            external_id (str):  A string to be used as ID for external use
            external_type (str):  Type of the external ID

        Returns:
            ManagedObject instance
        """

        object_id = await self.get_id(external_id, external_type)
        return await Inventory(self.c8y).get(object_id)

    async def get_all(self, object_id: str) -> list[ExternalId]:
        """Read all external IDs for a managed object.

        Args:
            object_id (str):  Valid database ID of a managed object

        Returns:
            A list of ExternalId instances (can be empty)
        """
        result = await self.c8y.get(_build_resource_path(object_id))
        return [ExternalId.from_json(x, c8y=self.c8y) for x in result["externalIds"]]
