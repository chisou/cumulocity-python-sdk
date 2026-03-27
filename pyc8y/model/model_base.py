import asyncio
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import re
from typing import (
    Any,
    Generic,
    TypeVar,
    Self,
    Mapping,
    Callable,
    AsyncIterator,
    Awaitable,
    Sequence,
)

from pyc8y.rest import CumulocityRestClient, BatchError
from pyc8y.base_util import flatten, is_sequence
from pyc8y.model.model_util import (
    as_tuple,
    as_record,
    get_by_path,
    to_datetime,
    to_pascal_case,
    now_datetime,
    to_timestring,
    now_timestring,
)
# trying to import various matchers that need external libraries
try:
    from pyc8y.model.matcher import PydfMatcher as DefaultMatcher
except ImportError:
    try:
        from pyc8y.model.matcher import JmesPathMatcher as DefaultMatcher
    except ImportError:
        try:
            from pyc8y.model.matcher import JsonPathMatcher as DefaultMatcher
        except ImportError:
            DefaultMatcher = None
from pyc8y.types import InventoryMeta, ResourceMeta, AsValuesSpec, MatcherSpec, ParamsSpec

CO = TypeVar("CO", bound="CumulocityObject")


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
    except ValueError as e:
        raise ValueError(f"Invalid datetime{param_name()} ({e}).")


def expand_dotted(kwargs):
    if not kwargs:
        return kwargs

    result = {}
    for key, value in kwargs.items():
        parts = key.split(".")
        current = result

        for part in parts[:-1]:
            current = current.setdefault(part, {})

        current[parts[-1]] = value

    return result


def json_property(key: str, read_only=False) -> property:
    def getter(self):
        return self._json[key]
    def setter(self, value):
        if value is not None:
            self._staged_json[key] = value
    return property(getter) if read_only else property(getter, setter)


def id_property(key: str, read_only=False) -> property:
    def getter(self):
        return self._json[key]["id"]
    def setter(self, value):  # todo: not sure we ever need a setter for ID
        if value is not None:
            self._staged_json[key] = {"id": value}
    return property(getter) if read_only else property(getter, setter)


def tag_property(key: str, read_only=False) -> property:
    def getter(self):
        return key in self._json
    def setter(self, value):
        self._staged_json[key] = {}
    return property(getter) if read_only else property(getter, setter)


def time_property(key: str, read_only=False) -> property:
    def getter(self):
        return self._json[key]
    def setter(self, value):
        if value is not None:
            self._staged_json[key] = coerce_timestring(value, key)
    return property(getter) if read_only else property(getter, setter)


def datetime_property(key: str) -> property:
    def getter(self):
        return to_datetime(self._json[key])
    return property(getter)


def map_params(
        *,
        name=None,
        fragment=None,
        bulk_id=None,
        series=None,
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
    ) -> Sequence[tuple[str, str]]:
    def multi(*xs):
        return sum(bool(x) for x in xs) > 1

    if multi(min_age, before, date_to):
        raise ValueError("Only one of 'min_age', 'before' and 'date_to' query parameters must be used.")
    if multi(max_age, after, date_from):
        raise ValueError("Only one of 'max_age', 'after' and 'date_from' query parameters must be used.")
    if multi(created_from, created_after):
        raise ValueError("Only one of 'created_from' and 'created_after' query parameters must be used.")
    if multi(created_to, created_before):
        raise ValueError("Only one of 'created_to' and 'created_before' query parameters must be used.")
    if multi(last_updated_from, updated_after):
        raise ValueError("Only one of 'last_updated_from' and 'updated_after' query parameters must be used.")
    if multi(last_updated_to, updated_before):
        raise ValueError("Only one of 'last_updated_to' and 'updated_before' query parameters must be used.")

    if (not source) and any([with_source_devices, with_source_assets]):
        raise ValueError("Can only include source assets/devices if 'source' parameter is provided.")

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

    series = series if is_sequence(series) else (series,) if series else ()
    params = (
        ("name", name),  # TODO, check if OData encoding works as expected
        ("fragmentType", fragment),
        ("source", source),
        ("bulkOperationId", bulk_id),
        ('dateFrom', date_from),
        ('dateTo', date_to),
        ('createdFrom', created_from),
        ('createdTo', created_to),
        ('lastUpdatedFrom', updated_from),
        ('lastUpdatedTo', updated_to),
        ("revert", encode(reverse)),
        *(("series", s) for s in series),
        *((k, encode(v)) for k, v in kwargs.items())
    )
    return [
        (to_pascal_case(k), str(v))
        for k, v in params
        if v is not None
    ]

def encode(value: Any | None) -> Sequence | str | None:
    if value is None:
        return None
    if is_sequence(value):
        return tuple(encode(x) for x in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value  # encode?
    raise ValueError(f"Unexpected value type '{type(value)}'. No idea how to encode.")


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


class CumulocityObject:
    """Base class for all Cumulocity database objects."""
    _meta: ResourceMeta

    def __init__(self, c8y: CumulocityRestClient | None = None, **kwargs):
        self.c8y = c8y
        self._source_json: dict | None = {}
        self._staged_json: dict | None = expand_dotted(kwargs)

    @property
    def _json(self) -> dict:
        if not self._staged_json:
            return self._source_json
        if not self._source_json:
            return self._staged_json
        return self._source_json | self._staged_json

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
    def _build(cls, json: dict, c8y: CumulocityRestClient | None = None) -> Self:
        obj = cls()  # this might set default values which classifies as "updated"
        obj._source_json = json
        obj._staged_json = {}  # reset all updates
        obj.c8y = c8y
        return obj

    @classmethod
    def from_json(cls, json: dict, c8y: CumulocityRestClient | None = None) -> Self:
        return cls._build(json, c8y=c8y)

    def to_json(self, only_updated=False) -> dict:
        return self._staged_json if only_updated else self._json

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
            self._staged_json[path] = value
            return

        # copy the entire source branch to allow partial updates
        if keys[0] not in self._staged_json:
            staged = deepcopy(self._source_json.get(keys[0], {}))
        else:
            staged = self._staged_json[keys[0]]
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
        self._staged_json[keys[0]] = staged

    def __setitem__(self, path, value):
        self._set(path, value, fail=True)

    def set(self, path, value):
        self._set(path, value, fail=False)

    def __iadd__(self, other) -> Self:
        if not is_sequence(other):
            other = (other,)
        for i in other:
            self._staged_json[i.name] = i.items
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
                self._meta.resource_path,
                json=self.to_json(),
                accept=self._meta.object_mime_type,
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
                accept=self._meta.object_mime_type,
                content_type=self._meta.object_mime_type,
        )
        if inplace:
            self._source_json = object_json
            return self
        return self._build(object_json, c8y=self.c8y)


    async def _apply_to(self, other_id: str | int) -> Self:
        """Apply changes made to this object to another object in the database.

        Args:
            other_id (str):  Database ID of the object to update.

        Returns:
            A fresh object representing the updated object's state within
            the database.
        """
        assert_c8y(self)
        return self._build(
            json=await self.c8y.put(
                self._meta.build_object_path(other_id),
                json=self.to_json(only_updated=True),
                accept=self._meta.object_mime_type,
                content_type=self._meta.object_mime_type
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
                accept=self._meta.object_mime_type,
        )
        if inplace:
            self._source_json = object_json
            return self
        return self._build(object_json, c8y=self.c8y)


    async def delete(self, **_) -> None:  # allow override with parameters
        """Delete the object within the database."""
        await self._delete()


class CumulocityResource(Generic[CO]):
    """Abstract base class for all Cumulocity API resources."""
    _meta = InventoryMeta
    _object_type: type[CO]

    def __init__(self, c8y: CumulocityRestClient):
        self.c8y = c8y
        self.default_matcher = DefaultMatcher

    @property
    def resource_path(self) -> str:
        return self._meta.resource_path

    @property
    def object_mime_type(self) -> str:
        return self._meta.object_mime_type

    @property
    def collection_mime_type(self) -> str:
        return self._meta.collection_mime_type

    @classmethod
    def build_object_path(cls, object_id: str) -> str:
        """Build the path to a specific object of this resource.

        Args:
            object_id (int|str):  Cumulocity ID of the object

        Returns:
            The relative path to the object within Cumulocity.
        """
        return cls._meta.build_object_path(object_id)

    async def _get(self, object_id: str, **kwargs) -> CO:
        return self._object_type.from_json(
            await self.c8y.get(
                self.build_object_path(object_id),
                params=map_params(**kwargs),
                accept=self._meta.object_mime_type,
            ),
            c8y=self.c8y,  # inject c8y instance
        )

    async def _get_last(self, expression: str | None, params: dict | None, as_values) -> CO | Any | tuple[Any] | None:
        if expression:
            result_json = await self.c8y.get(
                f"{self.resource_path}?{expression}&currentPage=1&pageSize=1",
                accept=self._meta.object_mime_type
            )
        else:
            result_json = await self.c8y.get(self.resource_path, params, accept=self._meta.collection_mime_type)
        results = result_json[self._meta.collection_name]
        if not results:
            return None
        if as_values:
            return as_tuple(results[0], as_values)
        return self._object_type.from_json(results[0], c8y=self.c8y)

    async def _get_count(self, expression: str | None, params: Sequence[tuple[str, str]] | None) -> int:
        if expression:
            result_json = await self.c8y.get(f"{self.resource_path}?{expression}&pageSize=1&withTotalPages=true")
        else:
            # params are not merged, but we can be sure that page size etc. are not part of params
            result_json = await self.c8y.get(self.resource_path, (*params, ("pageSize", "1"), ("withTotalPages", "true")))
        return result_json["statistics"]["totalPages"]

    async def _iterate(
            self,
            *,
            expression: str | None = None,
            params: ParamsSpec = None,
            page_number: int | None = None,
            limit: int | None = None,
            include: MatcherSpec = None,
            exclude: MatcherSpec = None,
            as_values: AsValuesSpec = None,
    ) -> AsyncIterator[CO | Any | tuple[CO]]:
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
                response_json = await self.c8y.get(f"{self.resource_path}?{expression}&currentPage={current_page}")
            else:
                response_json = await self.c8y.get(self.resource_path, (*params, ("currentPage", current_page)))
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
                    yield self._object_type.from_json(json, c8y=self.c8y)
                num_results = num_results + 1
            # when a specific page was specified we don't read more pages
            if page_number:
                break
            # continue with next page
            current_page = current_page + 1

    async def _create(self, *objects: CO, workers: int | None = None) -> None:
        await run_batched(
            flatten(objects),
            workers,
            lambda x: self.c8y.post(self.resource_path, json=x.to_json(), accept=None)
        )

    async def _create_bulk(self, *objects: CO) -> None:
        objects = flatten(objects)  # not documented, but good to have
        bulk_json = {self._meta.collection_name: [o.to_json() for o in objects]}
        await self.c8y.post(self.resource_path, bulk_json, content_type=self.collection_mime_type)

    async def _update(self, *objects: CO, workers: int | None = None) -> None:
        await run_batched(
            flatten(objects),
            workers,
            lambda x: self.c8y.put(self.build_object_path(x.id), json=x.to_json(only_updated=True), accept=None)
        )

    async def _apply_to(self, model: dict | CO, *objects: str | CO, workers: int | None = None) -> None:
        model_json = model if isinstance(model, dict) else model.to_json(only_updated=True)
        await run_batched(
            ensure_ids(flatten(objects)),
            workers,
            lambda x: self.c8y.put(self.build_object_path(x), model_json, content_type=self._meta.object_mime_type, accept=None)
        )

    # this one should be ok for all implementations, hence we define it here
    async def _delete(self, *objects: str | CO, workers: int | None = None) -> None:
        await run_batched(
            ensure_ids(flatten(objects)),
            workers,
            lambda x: self.c8y.delete(self.build_object_path(x)),
        )


def ensure_ids(objects):
    try:
        return [o.id for o in objects]  # noqa (id)
    except AttributeError:
        return objects


async def run_batched(things: Sequence[Any], workers: int | None, op: Callable[[Any], Awaitable[Any]]) -> None:
    if workers is None:
        for thing in things:
            await op(thing)
        return

    errors: list[BaseException] = []
    for i in range(0, len(things), workers):
        batch = things[i : i + workers]
        results = await asyncio.gather(*(op(thing) for thing in batch), return_exceptions=True)
        errors.extend(r for r in results if isinstance(r, BaseException))

    if errors:
        raise BatchError(errors)
