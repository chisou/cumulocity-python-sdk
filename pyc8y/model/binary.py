# Copyright (c) 2026 Christoph Souris
from os import PathLike
from typing import BinaryIO, AsyncIterator, Any, Self

import orjson

from pyc8y.rest import CumulocityRestClient
from pyc8y.model.matcher import JsonMatcher
from pyc8y.model.managed_object import ManagedObject
from pyc8y.model.model_base import (
    CumulocityResource,
    json_property,
    map_params,
    assert_c8y,
    assert_id,
)
from pyc8y.types import BinariesMeta, AsValuesSpec


class Binary(ManagedObject):
    """Represents a binary object/file within the Database.

    See also: https://cumulocity.com/api/core/#tag/Binaries
    """
    _meta = BinariesMeta

    def __init__(
            self,
            c8y: CumulocityRestClient | None = None,
            *,
            type: str | None = None,   # noqa (type)
            name: str | None = None,
            owner: str | None = None,
            content_type: str | None = None,
            file: str | PathLike | BinaryIO | None = None,
            **kwargs
    ):
        filename = None
        if isinstance(file, str):
            filename = file
        super().__init__(c8y, type=type or content_type, name=name or filename, owner=owner, **kwargs)
        self.file = file
        self.content_type = content_type or type

    content_type = json_property("contentType")
    length = json_property("length", read_only=True)

    @classmethod
    def from_json(cls, json: dict, c8y: CumulocityRestClient | None = None) -> Self:
        return cls._build(json, c8y=c8y)

    async def create(self) -> Self:
        """Create a new binary within the database by uploading the file.

        Returns:
            A fresh Binary instance representing the created object.

        Raises:
            FileNotFoundError:  if the file attribute refers to an invalid path
        """
        assert_c8y(self)
        result_json = await self.c8y.post_file(
            self._meta.resource_path,
            file=self.file,
            filename=self.name,
            form_data={"object": orjson.dumps(self.to_json()).decode("utf8")},
            content_type=self.get("content_type"),
        )
        return Binary.from_json(result_json, c8y=self.c8y)

    async def update(self, inplace: bool = True) -> Self:
        """Update the binary attachment.

        Returns:
            A fresh Binary instance representing the updated object.

        Raises:
            FileNotFoundError:  if the file attribute refers to an invalid path
        """
        assert_c8y(self)
        assert_id(self)
        result_json = await self.c8y.put_file(
            self.object_path,
            file=self.file,
            content_type=self.get("content_type"),
        )
        if inplace:
            self._source_json = result_json
            return self
        return self._build(result_json, c8y=self.c8y)

    async def read_file(self) -> bytes:
        """Read the content of the binary attachment.

        Returns:
            The binary attachment's content as bytes
        """
        assert_c8y(self)
        assert_id(self)
        return await Binaries(self.c8y).read_file(self.id)


class Binaries(CumulocityResource[Binary]):
    """Provides access to the Binaries API.

    See also: https://cumulocity.com/api/core/#tag/Binaries
    """
    _meta = BinariesMeta
    _object_type = Binary

    async def read_file(self, id: str) -> bytes:  # noqa (id)
        """Read the binary content of a specific binary.

        Args:
            id (str):  The database ID of the binary object

        Returns:
            The binary attachment's content as bytes
        """
        return await self.c8y.get_file(self.build_object_path(id))

    async def upload(self, file: str | PathLike | BinaryIO, name: str, type: str) -> Binary:  # noqa (type)
        """Upload a file.

        Args:
            file (str|file-like):  File to upload
            name (str):  Virtual name of the file
            type (str):  MIME type of the file

        Returns:
            A Binary instance referencing the uploaded file

        Raises:
            FileNotFoundError:  if the file refers to an invalid path
        """
        result_json = await self.c8y.post_file(
            self.resource_path,
            file=file,
            filename=name,
            form_data={"object": orjson.dumps({"name": name, "type": type}).decode("utf8")},
            content_type=type,
        )
        return Binary.from_json(result_json, c8y=self.c8y)

    async def create(self, *binaries: Binary) -> int:
        """Create binaries, i.e. upload files.

        Each of the binaries must have a `file` attribute set.

        Args:
            *binaries (Binary):  Binaries to upload

        Returns:
            The number of successfully created binaries

        Raises:
            FileNotFoundError:  if one of the file attributes refers to an invalid path
        """
        n = 0
        for b in binaries:
            await self.c8y.post_file(
                self.resource_path,
                file=b.file,
                filename=b.name,
                form_data={"object": orjson.dumps(b.to_json()).decode("utf8")},
                content_type=b.get('content_type'),
            )
            n += 1
        return n

    async def update(self, id: str, file: str | PathLike | BinaryIO, type: str | None = None) -> None:  # noqa (type,id)
        """Update a binary attachment.

        Args:
            id (str):  ID of an existing Binary within Cumulocity
            file (str|file-like):  File to upload
            type (str):  Content type of the file
        """
        await self.c8y.put_file(self.build_object_path(id), file=file, content_type=type)

    async def delete(self, *objects: str | Binary, workers: int | None = None) -> None:
        return await self._delete(*objects, workers=workers)

    def select(
            self,
            *,
            ids: list[str] | None = None,
            type: str | None = None,   # noqa (type)
            owner: str | None = None,
            child_device: str | None = None,
            child_asset: str | None = None,
            child_addition: str | None = None,
            include: str | JsonMatcher | None = None,
            exclude: str | JsonMatcher | None = None,
            limit: int | None = None,
            page_size: int = 1000,
            page_number: int | None = None,
            as_values: AsValuesSpec | None = None,
            workers: int | None = None,
            **kwargs
    ) -> AsyncIterator[Binary | Any | tuple[Any]]:
        """Query the database for binaries and iterate over the results.

        Args:
            ids (list):  Specific object IDs to select
            type (str):  Object type filter
            owner (str):  Username of the object owner
            child_device (str):  Object ID of a child device
            child_asset (str):  Object ID of a child asset
            child_addition (str):  Object ID of a child addition
            include (str|JsonMatcher):  Client-side inclusion filter
            exclude (str|JsonMatcher):  Client-side exclusion filter
            limit (int):  Limit the number of results
            page_size (int):  Number of records read per request
            page_number (int):  Pull a specific page only
            as_values:  Extract values at JSON paths as tuples
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of Binary instances
        """
        params = map_params(
            type=type,
            owner=owner,
            page_size=page_size,
            ids=ids,
            childDeviceId=child_device,
            childAssetId=child_asset,
            childAddition=child_addition,
            **kwargs,
        )
        return self._iterate(
            params=params,
            page_number=page_number,
            limit=limit,
            include=include,
            exclude=exclude,
            as_values=as_values,
            workers=workers,
        )

    async def get_all(
            self,
            *,
            ids: list[str] | None = None,
            type: str | None = None,   # noqa (type)
            owner: str | None = None,
            child_device: str | None = None,
            child_asset: str | None = None,
            child_addition: str | None = None,
            include: str | JsonMatcher | None = None,
            exclude: str | JsonMatcher | None = None,
            limit: int | None = None,
            page_size: int = 1000,
            page_number: int | None = None,
            as_values: AsValuesSpec | None = None,
            workers: int | None = None,
            **kwargs
    ) -> list[Binary | Any | tuple[Any]]:
        """Query the database for binary objects and return the results as list.

        See `select` for a documentation of arguments.

        Returns:
            List of Binary instances
        """
        return [x async for x in self.select(
            ids=ids,
            type=type,
            owner=owner,
            child_device=child_device,
            child_asset=child_asset,
            child_addition=child_addition,
            include=include,
            exclude=exclude,
            limit=limit,
            page_size=page_size,
            page_number=page_number,
            as_values=as_values,
            workers=workers,
            **kwargs,
        )]

    async def get_count(
            self,
            *,
            ids: list[str] | None = None,
            type: str | None = None,   # noqa (type)
            owner: str | None = None,
            child_device: str | None = None,
            child_asset: str | None = None,
            child_addition: str | None = None,
            **kwargs
    ) -> int:
        """Calculate the number of potential results of a database query.

        Returns:
            Number of potential results
        """
        params = map_params(
            type=type,
            owner=owner,
            page_size=1,
            ids=ids,
            childDeviceId=child_device,
            childAssetId=child_asset,
            childAddition=child_addition,
            **kwargs,
        )
        return await self._get_count(expression=None, params=params)
