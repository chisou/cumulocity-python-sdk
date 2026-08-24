# Copyright (c) 2026 Christoph Souris
import io
import os
from typing import AsyncIterator, Self, Sequence, Any

import orjson

from pyc8y.rest import CumulocityRestClient, FileDownload
from pyc8y.model.matcher import JsonMatcher
from pyc8y.model.managed_object import ManagedObject
from pyc8y.model.model_base import (
    CumulocityResource,
    json_property,
    map_params,
    resolve_page_size,
    run_batched,
)
from pyc8y.types import BinaryMeta


class Binary(ManagedObject):
    """Represents a binary object/file within the Database.

    See also: https://cumulocity.com/api/core/#tag/Binaries
    """

    _meta = BinaryMeta

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        *,
        type: str | None = None,  # noqa (type)
        name: str | None = None,
        owner: str | None = None,
        content_type: str | None = None,
        file: str | os.PathLike | io.IOBase | None = None,
        **kwargs,
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

    async def create(self, copy: bool = False) -> Self:
        """Create a new binary within the database by uploading the file.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The created Binary. By default, this is `self`; if `copy=True`,
            a fresh instance.

        Raises:
            FileNotFoundError:  if the file attribute refers to an invalid path
        """
        self._assert_c8y()
        result_json = await self.c8y.post_file(
            self.resource_path,
            file=self.file,
            filename=self.name,
            form_data={"object": orjson.dumps(self.json).decode("utf8")},
            content_type=self.get("content_type"),
        )
        if copy:
            return self._build(result_json, c8y=self.c8y)
        self._source_json = result_json
        return self

    async def update(self, copy: bool = False) -> Self:
        """Update the binary attachment.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated Binary. By default, this is `self`; if `copy=True`,
            a fresh instance.

        Raises:
            FileNotFoundError:  if the file attribute refers to an invalid path
        """
        self._assert_c8y()
        self._assert_key()
        result_json = await self.c8y.put_file(
            self.object_path,
            file=self.file,
            content_type=self.get("content_type"),
        )
        if copy:
            return self._build(result_json, c8y=self.c8y)
        self._source_json = result_json
        return self

    async def read_file(self) -> FileDownload:
        """Read the content of the binary attachment.

        Returns:
            A FileDownload tuple of file content bytes and filename.
        """
        self._assert_c8y()
        self._assert_key()
        return await Binaries(self.c8y).read_file(self.id)


class Binaries(CumulocityResource[Binary]):
    """Provides access to the Binaries API.

    See also: https://cumulocity.com/api/core/#tag/Binaries
    """

    _meta = BinaryMeta
    _object_type = Binary

    async def read_file(self, id: str) -> FileDownload:  # noqa (id)
        """Read the binary content of a specific binary.

        Args:
            id (str):  The database ID of the binary object

        Returns:
            A FileDownload tuple of file content bytes and filename.
        """
        return await self.c8y.get_file(self.build_object_path(id))

    async def upload(self, file: str | os.PathLike | io.IOBase, name: str, type: str) -> Binary:  # noqa (type)
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

    async def create(self, *binaries: Binary, workers: int | None = None) -> int:
        """Create binaries, i.e. upload files.

        Each of the binaries must have a `file` attribute set.

        Args:
            *binaries (Binary):  Binaries to upload
            workers (int):  Number of parallel workers

        Returns:
            The number of created binaries

        Raises:
            FileNotFoundError:  if one of the file attributes refers to an invalid path
        """
        await run_batched(
            binaries,
            workers,
            lambda b: self.c8y.post_file(
                self.resource_path,
                file=b.file,
                filename=b.name,
                form_data={"object": orjson.dumps(b.json).decode("utf8")},
                content_type=b.get("content_type"),
            ),
        )
        return len(binaries)

    async def update(self, id: str, file: str | os.PathLike | io.IOBase, type: str | None = None) -> None:  # noqa (type,id)
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
        expression: str | None = None,
        *,
        ids: Sequence[str] | None = None,
        type: str | None = None,  # noqa (type)
        owner: str | None = None,
        child_device: str | None = None,
        child_asset: str | None = None,
        child_addition: str | None = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | Sequence[str | tuple[str, Any]] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[Binary]:
        """Query the database for binaries and iterate over the results.

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided
            ids (list):  Specific object IDs to select
            type (str):  Object type filter
            owner (str):  Username of the object owner
            child_device (str):  Object ID of a child device
            child_asset (str):  Object ID of a child asset
            child_addition (str):  Object ID of a child addition
            include (str|JsonMatcher):  Client-side inclusion filter
            exclude (str|JsonMatcher):  Client-side exclusion filter
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int):  Pull a specific page only
            as_values:  Extract values at JSON paths as tuples
            workers (int):  Number of parallel page-fetch workers

        Returns:
            AsyncIterator of Binary instances
        """
        page_size = resolve_page_size(page_size, limit, include, exclude)
        params = (
            map_params(
                type=type,
                owner=owner,
                page_size=page_size,
                ids=ids,
                childDeviceId=child_device,
                childAssetId=child_asset,
                childAddition=child_addition,
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
        ids: Sequence[str] | None = None,
        type: str | None = None,  # noqa (type)
        owner: str | None = None,
        child_device: str | None = None,
        child_asset: str | None = None,
        child_addition: str | None = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | Sequence[str | tuple[str, Any]] | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[Binary]:
        """Query the database for binary objects and return the results as list.

        See `select` for a documentation of arguments.

        Returns:
            List of Binary instances
        """
        return [
            x
            async for x in self.select(
                expression=expression,
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
            )
        ]

    async def get_count(
        self,
        expression: str | None = None,
        *,
        ids: Sequence[str] | None = None,
        type: str | None = None,  # noqa (type)
        owner: str | None = None,
        child_device: str | None = None,
        child_asset: str | None = None,
        child_addition: str | None = None,
        **kwargs,
    ) -> int:
        """Calculate the number of potential results of a database query.

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided

        Returns:
            Number of potential results
        """
        params = (
            map_params(
                type=type,
                owner=owner,
                page_size=1,
                ids=ids,
                childDeviceId=child_device,
                childAssetId=child_asset,
                childAddition=child_addition,
                **kwargs,
            )
            if not expression
            else ()
        )
        return await self._get_count(expression=expression, params=params)
