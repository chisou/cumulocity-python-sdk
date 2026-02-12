from __future__ import annotations

import asyncio
from abc import ABC
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import re
from typing import Any, Generic, TypeVar, Self, AsyncGenerator, Mapping, Callable, ClassVar, Sequence, Iterable

from pyc8y.base import CumulocityRestApi, BatchError
from pyc8y.model.matcher import JsonMatcher
from pyc8y.model.model_util import (
    as_tuple,
    as_record,
    get_by_path,
    to_datetime,
    to_pascal_case,
    now_datetime, to_timestring, now_timestring, is_sequence,
)
from pyc8y.types import InventoryMeta, ResourceMeta

T = TypeVar("T", bound="CumulocityObject")

def assert_c8y(obj):
    """Assert that a model object has a Cumulocity connection."""
    if not obj.c8y:
        raise ValueError("Cumulocity connection reference must be set to allow direct database access.")


def assert_id(obj):
    """Assert that a model object has a Cumulocity connection."""
    if not obj.id:
        raise ValueError("The object ID must be set to allow direct object access.")


def coerce_datetime(value: str | datetime | None, name: str = None) -> datetime | None:
    """Ensure a proper datetime object."""
    def param_name():
        return f" ({name})" if name else ""

    if value is None:
        return None
    if isinstance(value, datetime):
        if not value.tzinfo:
            raise ValueError(f"A specified datetime{param_name()} needs to be timezone aware.")
        return value
    try:
        value = to_datetime(value)
        if value.tzinfo is None:
            value = value.replace(tzinfo = timezone.utc)
        return value
    except ValueError:
        raise ValueError(f"Unable to convert to datetime{param_name()}.")


def coerce_timedelta(value: str | timedelta | None, name: str = None) -> timedelta | None:
    def param_name():
        return f" ({name})" if name else ""

    if value is None:
        return None
    if isinstance(value, timedelta):
        return value

    if ":" in value:
        try:
            parts = value.split(":")
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2]) if len(parts) > 2 else 0
            return timedelta(hours=hours, minutes=minutes, seconds=seconds)
        except ValueError as e:
            raise ValueError(f"Invalid timedelta{param_name()}: {value!r}")

    # find first non-digit
    parts = re.split(r"([dDhHmMsS])", value)
    if len(parts) < 3 or not parts[0].isdigit():
        raise ValueError(f"Invalid timedelta{param_name()}: {value!r}")

    amount = int(parts[0])
    unit = parts[1].lower()

    if unit == "d":
        return timedelta(days=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "s":
        return timedelta(seconds=amount)

    raise ValueError(f"Invalid timedelta{param_name()}: {value!r}")


def coerce_timestring(value: str | datetime | None, name: str = None) -> str | None:
    """Ensure that a given timestring reflects a proper, timezone aware date/time.
    A static string 'now' will be converted to the current datetime in UTC."""
    def param_name():
        return f" ({name})" if name else ""

    if value is None:
        return None
    if isinstance(value, datetime):
        if not value.tzinfo:
            raise ValueError(f"A specified datetime{param_name()} needs to be timezone aware.")
        return to_timestring(value)
    if value == "now":
        return now_timestring()
    try:
        value = to_datetime(value)
        if value.tzinfo is None:
            value = value.replace(tzinfo = timezone.utc)
        return to_timestring(value)
    except ValueError:
        raise ValueError(f"Invalid datetime{param_name()}.")


def json_property(key: str, read_only=False) -> property:
    def getter(self):
        return self._json[key]
    def setter(self, value):
        self._update_json[key] = value
    return property(getter) if read_only else property(getter, setter)


def id_property(key: str, read_only=False) -> property:
    def getter(self):
        return self._json[key]["id"]
    def setter(self, value):  # todo: not sure we ever need a setter for ID
        self._update_json[key] = {"id": value}
    return property(getter) if read_only else property(getter, setter)


def tag_property(key: str, read_only=False) -> property:
    def getter(self):
        return key in self._json
    def setter(self, value):
        self._update_json[key] = {}
    return property(getter) if read_only else property(getter, setter)


def time_property(key: str, read_only=False) -> property:
    def getter(self):
        return self._json[key]
    def setter(self, value):
        self._update_json[key] = coerce_timestring(value, key)
    return property(getter) if read_only else property(getter, setter)


def datetime_property(key: str) -> property:
    def getter(self):
        return to_datetime(self._json[key])
    return property(getter)


def map_params(
        name=None,
        fragment=None,
        bulk_id=None,
        before=None,
        after=None,
        date_from=None,
        date_to=None,
        created_before=None,
        created_after=None,
        created_from=None,
        created_to=None,
        updated_before=None,
        updated_after=None,
        last_updated_from=None,
        last_updated_to=None,
        min_age=None,
        max_age=None,
        source=None,
        with_source_assets=None,
        with_source_devices=None,
        reverse=None,
        **kwargs
    ) -> dict:
    if min_age:
        date_to = now_datetime() - coerce_timedelta(min_age)
    if max_age:
        date_from = now_datetime() - coerce_timedelta(max_age)

    date_from = coerce_timestring(date_from, "date_from") or coerce_timestring(after, "after")
    date_to = coerce_timestring(date_to, "date_to") or coerce_timestring(before, "before")
    created_from = coerce_timestring(created_from, "created_from") or coerce_timestring(created_after, "created_after")
    created_to = coerce_timestring(created_to, "created_to") or coerce_timestring(created_before, "created_before")
    updated_from = coerce_timestring(last_updated_from, "last_updated_from") or coerce_timestring(updated_after, "updated_after")
    updated_to = coerce_timestring(last_updated_to, "last-updated_to") or coerce_timestring(updated_before, "updated_before")

    if (not source) and any([with_source_devices, with_source_assets]):
        raise ValueError("Can only include source assets/devices if 'source' parameter is provided.")

    # perform abbreviated -> actual parameter names
    params = {
        "name": name,  # TODO: check if OData encoding works as expected
        "fragmentType": fragment,
        "bulkOperationId": bulk_id,
        'dateFrom': date_from,
        'dateTo': date_to,
        'createdFrom': created_from,
        'createdTo': created_to,
        'lastUpdatedFrom': updated_from,
        'lastUpdatedTo': updated_to,
        "revert": reverse,
        **kwargs,
    }
    return {
        to_pascal_case(k): str(v)
        for k, v in params.items()
        if v is not None
    }


class AttrDict:
    """Minimal implementation.
    Known issues:
        - breaks identity checks `obj.a is obj.a` (because AttrDict is instantiated on each access.
        - doesn't have any "internal attribute" check, so technically `obj._d = something` would destroy the instance
    """
    __slots__ = ("_d", "_cb")

    def __init__(self, d: Mapping, cb: Callable | None):
        object.__setattr__(self, "_d", d)
        object.__setattr__(self, "_cb", cb)


    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __getitem__(self, key):
        if key in self._d:
            value =self._d[key]
        else:
            pascal_key = to_pascal_case(key)
            if pascal_key in self._d:
                value = self._d[pascal_key]
            else:
                raise AttributeError(f"No such attribute: {key} (or {pascal_key})")

        if isinstance(value, Mapping):
            value = AttrDict(value, self._cb)
        return value

    def __setattr__(self, key, value):
        self._d[key] = value
        if self._cb is not None:
            self._cb()


class CumulocityObject(Generic[T]):
    """Base class for all Cumulocity database objects."""
    _meta: ResourceMeta

    def __init__(self, c8y: CumulocityRestApi | None = None, **kwargs):
        self.c8y = c8y
        self._source_json: dict | None = kwargs
        self._update_json: dict = {}
        self._staged_json: dict = {}

    @property
    def _json(self) -> dict:
        if not self._update_json:
            return self._source_json
        if not self._source_json:
            return self._update_json
        return self._source_json | self._update_json

    @property
    def id(self):
        # id can never come from update
        return self._source_json.get("id", None)

    @property
    def object_path(self) -> str:
        return self._meta.build_object_path(self.id)

    def __repr__(self) -> str:
        return ''.join([   # -> ClassName(id=123, type=abc)
            type(self).__name__,
            "(",
            ", ".join([
                f"{n}={getattr(self, n)}"
                for n in ["id", "type"] if getattr(self, n) is not None
            ]),
            ")"
        ])

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def _build(cls, json: dict, c8y: CumulocityRestApi | None = None) -> Self:
        obj = cls()  # this might set default values which classifies as "updated"
        obj._source_json = json
        obj._update_json = {}  # reset all updates
        obj.c8y = c8y
        return obj

    @classmethod
    def from_json(cls, json: dict, c8y: CumulocityRestApi | None = None) -> Self:
        return cls._build(json, c8y=c8y)

    def to_json(self, only_updated=False) -> dict:
        return self._update_json if only_updated else self._json

    def __contains__(self, path) -> bool:
        current = self._json
        for key in path.split('.'):
            if not isinstance(current, Mapping):
                return False
            if key in current:
                current = current[key]
            elif to_pascal_case(key) in current:
                current = current[to_pascal_case(key)]
            else:
                return False
        return True

    def has(self, path):
        assert path in self

    def __getitem__(self, path) -> Any:
        return get_by_path(self._json, path, fail=True)

    def get(self, path, default: Any = None) -> Any:
        return get_by_path(self._json, path, default=default)

    # def __getattr__(self, name: str):
    #     """ Get the value of a custom fragment.
    #
    #     Depending on the definition the value can be a scalar or a
    #     complex structure (modeled as nested dictionary).
    #
    #     Args:
    #         name (str): Name of the custom fragment.
    #     """
    #     # check in update JSON
    #     pascal_name = to_pascal_case(name)
    #     if name in self._update_json or pascal_name in self._update_json:
    #         value = self._update_json.get(name, self._update_json[pascal_name])
    #         if isinstance(value, Mapping):
    #             return AttrDict(value, None)
    #
    #     if self._staged_json:
    #         if name in self._staged_json or pascal_name in self._staged_json:
    #             return self._staged_json.get(name, self._staged_json[pascal_name])  # already AttrDict
    #
    #     if name in self._source_json or pascal_name in self._source_json:
    #         value = self._source_json.get(name, self._source_json[pascal_name])
    #     else:
    #         raise AttributeError(f"No such attribute: {name} (or {pascal_name})")
    #     if isinstance(value, Mapping):
    #         def unstage():
    #             self._update_json[name] = self._staged_json[name]._d   # pylint: disable=protected-access
    #         value = AttrDict(deepcopy(value), unstage)
    #         self._staged_json[name] = value
    #
    #     return value

    def _set(self, path: str, value: Any, fail: bool):
        # TODO: print the "current" path in error messages for easier debugging
        keys = path.split('.')

        if len(keys) == 1:  # no path to drill down to -> direct assignment
            self._update_json[path] = value
            return

        # copy the entire source branch to allow partial updates
        if keys[0] not in self._update_json:
            staged = deepcopy(self._source_json.get(keys[0], {}))
        else:
            staged = self._update_json[keys[0]]
        current = staged

        for i, key in enumerate(keys[1:-1]):
            if not isinstance(current, Mapping):
                raise ValueError(f"Can't traverse into path: {path}")
            if key in current:
                current = current[key]
                continue
            if fail:
                if to_pascal_case(key) in current:
                    raise KeyError(f"Unable to find '{path}' in object JSON. Did you mean '{to_pascal_case(key)}'?")
                raise KeyError(f"Unable to find '{path}' in object JSON.")
            current[key] = {}
            current = current[key]

        current[keys[-1]] = value
        self._update_json[keys[0]] = staged

    def __setitem__(self, path, value):
        self._set(path, value, fail=True)

    def set(self, path, value):
        self._set(path, value, fail=False)

    def __iadd__(self, other) -> Self:
        if not is_sequence(other):
            other = (other,)
        for i in other:
            self._update_json[i.name] = i.items
        return self

    def as_tuple(self, *paths: str | tuple[str, Any]) -> tuple:
        return as_tuple(self._json, *paths)

    def as_record(self, mapping: dict[str, str | tuple[str | Any]]) -> dict:
        return as_record(self._json, mapping)

    async def _create(self) -> Self:
        """Create the object within the database.

        Returns:
            A fresh object representing what was created within the database;
            this includes the Cumulocity ID.
        """
        assert_c8y(self)
        return self._build(
            json=await self.c8y.post(
                self._c8y_api.resource_path,
                json=self.to_json(),
                accept=self._c8y_api.mime_type,
            ),
            c8y=self.c8y,
        )

    async def _update(self, inplace: bool = False) -> Self:  # TODO: shouldn't this best update itself?
        """Update the object within the database.

        Note: This will only send changed fields to increase performance.

        Returns:
            A fresh object representing the updated state within the database.
        """
        # TODO: to update itself - it would need to update the ._json variable?
        assert_c8y(self)
        assert_id(self)
        object_json = await self.c8y.put(
                self.object_path,
                json=self.to_json(True),
                accept=self._meta.mime_type,
                content_type=self._meta.mime_type,
        )
        if inplace:
            self._source_json = object_json
            return self
        return self._build(object_json, c8y=self.c8y)


    async def _apply_to(self, other_id: str | int) -> Self:
        """Apply changes made to this object to another object in the database.

        Args:
            other_id (str):  Database ID of the event to update.

        Returns:
            A fresh object representing the updated object's state within
            the database.
        """
        assert_c8y(self)
        return self._build(
            json=await self.c8y.put(
                self._meta.build_object_path(other_id),
                json=self.to_json(True),
                accept=self._meta.mime_type,
                content_type=self._meta.mime_type
            ),
            c8y=self.c8y
        )

    async def _delete(self, **params):
        assert_c8y(self)
        assert_id(self)
        await self.c8y.delete(self.object_path, params=params)

    async def _reload(self, inplace: bool = False) -> Self:
        assert_c8y(self)
        assert_id(self)
        object_json = await self.c8y.get(
                self.object_path,
                accept=self._meta.mime_type,
        )
        if inplace:
            self._source_json = object_json
            return self
        return self._build(object_json, c8y=self.c8y)


    async def delete(self, **_) -> None:  # allow override with parameters
        """Delete the object within the database."""
        await self._delete()


class CumulocityResource(ABC, Generic[T]):
    """Abstract base class for all Cumulocity API resources."""
    _meta = InventoryMeta
    object_type: type[T]

    def __init__(self, c8y: CumulocityRestApi):
        self.c8y = c8y
        self.default_matcher = None

    @property
    def resource_path(self) -> str:
        return self._meta.resource_path

    @property
    def mime_type(self) -> str:
        return self._meta.mime_type

    @classmethod
    def build_object_path(cls, object_id: int | str) -> str:
        """Build the path to a specific object of this resource.

        Args:
            object_id (int|str):  Cumulocity ID of the object

        Returns:
            The relative path to the object within Cumulocity.
        """
        return cls._meta.build_object_path(object_id)

    async def _get_object(self, object_id, **kwargs):
        return await self.c8y.get(self.build_object_path(object_id), params=map_params(**kwargs))

    async def _get_page(self, page_number: int, **kwargs):
        result_json = await self.c8y.get(self.resource_path, {**kwargs, "currentPage": page_number})  # todo: accept
        return result_json[self._meta.collection_name]

    async def _get_count(self, base_query: str) -> int:
        # the page_size=1 parameter must not be part of the query string
        sep = '&' if '?' in base_query else '?'
        kind = 'Pages' if 'binaries' in base_query else 'Pages'
        result_json = await self.c8y.get(f'{base_query}{sep}pageSize=1&withTotal{kind}=true')
        return result_json['statistics'][f'total{kind}']

    async def _iterate(
            self,
            expression: str | None = None,
            params: dict | None = None,
            page_number: int | None = None,
            limit: int | None = None,
            include: str | JsonMatcher | None = None,
            exclude: str | JsonMatcher | None = None,
            as_values: str | tuple[str, Any] | list[str | tuple[str|Any]] | None = None,
    ) -> AsyncGenerator[Any, None]:
        # if no specific page is defined we just start at 1
        current_page = page_number if page_number else 1
        # we will read page after page until
        #  - we reached the limit, or
        #  - there is no result (i.e. we were at the last page)
        num_results = 0
        # compile/prepare filter if defined
        if isinstance(include, str):
            if not self.default_matcher:
                raise ValueError("No default matcher defined (client-side filtering not supported?)")
            include = self.default_matcher(include)
        if isinstance(exclude, str):
            if not self.default_matcher:
                raise ValueError("No default matcher defined (client-side filtering not supported?)")
            exclude = self.default_matcher(exclude)

        while True:
            if expression:
                response_json = await self.c8y.get(f"{self.resource_path}?{expression}&currentPage={page_number}")
            else:
                response_json = await self.c8y.get(self.resource_path, {**params, "currentPage": page_number})
            obj_jsons = response_json[self._meta.collection_name]
            if not obj_jsons:
                break
            if include or exclude:
                obj_jsons = [
                    x for x in obj_jsons
                    if (not include or include.safe_matches(x))
                       and (not exclude or not exclude.safe_matches(x))
                ]
            for json in obj_jsons:
                if limit and num_results >= limit:
                    return
                if as_values:
                    yield as_tuple(json, as_values)
                else:
                    yield self.object_type.from_json(json, c8y=self.c8y)
                num_results = num_results + 1
            # when a specific page was specified we don't read more pages
            if page_number:
                break
            # continue with next page
            current_page = current_page + 1

    async def _get(self, object_id: str | int, **kwargs) -> T:
        obj_json = await self.c8y.get(self.build_object_path(object_id), params=map_params(**kwargs))
        obj = self.object_type(obj_json[self._meta.collection_name])
        obj.c8y = self.c8y
        return obj

    async def get(self, object_id: str | int, **_) -> T:
        return await self._get(object_id)

    async def _create(self, *objects: CumulocityObject | list[CumulocityObject]) -> None:
        if len(objects) == 1 and isinstance(objects[0], Iterable):  # should never be a string or something
            objects = tuple(objects[0])
        tasks = [
            asyncio.create_task(
                self.c8y.post(self.resource_path, json=o.to_json(), accept=None)
            )
            for o in objects
        ]
        errors = [x for x in await asyncio.gather(*tasks, return_exceptions=True) if isinstance(x, Exception)]
        if errors:
            raise BatchError(errors)

    async def _create_bulk(self, *objects: CumulocityObject | list[CumulocityObject]) -> None:
        bulk_json = {self._meta.collection_name: [o.to_json() for o in objects]}
        await self.c8y.post(self.resource_path, bulk_json, content_type=self.mime_type)  # TODO: mime type might be different for bulks?

    async def _update(self, *objects: CumulocityObject | list[CumulocityObject]) -> None:
        if len(objects) == 1 and isinstance(objects[0], Iterable):  # should never be a string or something
            objects = tuple(objects[0])
        tasks = [
            asyncio.create_task(
                self.c8y.put(self.build_object_path(o.id), json=o.to_json(only_updated=True), accept=None)
            )
            for o in objects
        ]
        errors = [x for x in await asyncio.gather(*tasks, return_exceptions=True) if isinstance(x, Exception)]
        if errors:
            raise BatchError(errors)

    async def _apply_to(self, model: dict | CumulocityObject, *object_ids: str | int) -> None:
        model_json = model if isinstance(model, dict) else model.to_json(only_updated=True)
        tasks = [
            asyncio.create_task(
                self.c8y.put(self.build_object_path(object_id), model_json, accept=None)
            )
            for object_id in object_ids
        ]
        errors = [x for x in await asyncio.gather(*tasks, return_exceptions=True) if isinstance(x, Exception)]
        if errors:
            raise BatchError(errors)

    # this one should be ok for all implementations, hence we define it here
    async def delete(self, *objects: str | int | CumulocityObject) -> None:
        """ Delete one or more objects within the database.

        The objects can be specified as instances of a database object
        (then, the id field needs to be defined) or simply as ID (integers
        or strings).

        Args:
            *objects (str):  Objects within the database specified by ID
                or as CumulocityObject instances
        """
        try:
            object_ids = [o.id for o in objects]  # noqa (id)
        except AttributeError:
            object_ids = objects
        tasks = [
            asyncio.create_task(
                self.c8y.delete(self.build_object_path(object_id))
            )
            for object_id in object_ids
        ]
        errors = [x for x in await asyncio.gather(*tasks, return_exceptions=True) if isinstance(x, Exception)]
        if errors:
            raise BatchError(errors)