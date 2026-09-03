import asyncio
from abc import abstractmethod
from collections import deque
from collections.abc import Mapping
from copy import deepcopy
from typing import (
    Any,
    Generic,
    TypeVar,
    Self,
    Callable,
    AsyncIterator,
    Awaitable,
    Sequence,
    Protocol,
    overload,
)

from pyc8y.rest import CumulocityRestClient, BatchError
from pyc8y.base_util import ensure_sequence, is_sequence
from pyc8y.model.model_util import (
    as_tuple,
    as_record,
    coerce_timedelta,
    coerce_timestring,
    expand_dotted,
    get_by,
    to_datetime,
    to_pascal_case,
    now_datetime,
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
from pyc8y.model.matcher import JsonMatcher
from pyc8y.types import InventoryMeta, ResourceMeta, DEFAULT_PAGE_SIZE

CO = TypeVar("CO", bound="CumulocityObject")
T = TypeVar("T")


def _extract_as_values(json: dict, as_values: str | tuple[str, Any] | Sequence[str | tuple[str, Any]]) -> Any:
    """Apply the collection-level `as_values` semantics: scalar in - scalar
    out, sequence in - tuple out."""
    if isinstance(as_values, list):
        return as_tuple(json, as_values)
    if isinstance(as_values, tuple):
        return get_by(json, as_values[0], as_values[1])
    return get_by(json, as_values)


class json_property(Generic[T]):
    """Descriptor for a JSON-backed property.

    Supports an optional type parameter for IDE type inference:
        name = json_property[str]("name")
    """

    def __init__(self, key: str, read_only: bool = False) -> None:
        self._key = key
        self._read_only = read_only

    @overload
    def __get__(self, obj: None, objtype: type) -> Self: ...
    @overload
    def __get__(self, obj: Any, objtype: type | None = None) -> T: ...

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.json.get(self._key)

    def __set__(self, obj: Any, value: T) -> None:
        if self._read_only:
            raise AttributeError(f"cannot set read-only property '{self._key}'")
        if value is not None:
            obj._staged_json[self._key] = value


def id_property(key: str, read_only=False) -> property:
    def getter(self):
        return self.json[key]["id"]

    def setter(self, value):  # todo: not sure we ever need a setter for ID
        if value is not None:
            self._staged_json[key] = {"id": value}

    return property(getter) if read_only else property(getter, setter)


def tag_property(key: str, read_only=False) -> property:
    def getter(self):
        return key in self.json

    def setter(self, _):
        self._staged_json[key] = {}

    return property(getter) if read_only else property(getter, setter)


def time_property(key: str, read_only=False) -> property:
    def getter(self):
        return self.json[key]

    def setter(self, value):
        if value is not None:
            self._staged_json[key] = coerce_timestring(value, key)

    return property(getter) if read_only else property(getter, setter)


def datetime_property(key: str) -> property:
    def getter(self):
        return to_datetime(self.json[key])

    return property(getter)


def references_property(collection: str, item: str) -> property:
    def getter(self):
        return {r[item]["id"] for r in self.json.get(collection, {}).get("references", [])}

    return property(getter)


def map_params(
    *,
    name=None,
    fragment=None,
    bulk_id=None,
    series=None,
    aggregation_function=None,
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
    revert=None,
    **kwargs,
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
    # Some Cumulocity collection endpoints (Measurements, Events, Operations)
    # only reliably apply `revert` ordering when a date range filter is also
    # present; force a wide-open one if ordering was requested but no bound
    # was otherwise given (same workaround each resource's `get_last` uses).
    if revert is not None and date_from is None and date_to is None:
        date_from = coerce_timestring("1970-01-01", "date_from")

    created_from = coerce_timestring(created_from, "created_from") or coerce_timestring(created_after, "created_after")
    created_to = coerce_timestring(created_to, "created_to") or coerce_timestring(created_before, "created_before")
    updated_from = coerce_timestring(last_updated_from, "last_updated_from") or coerce_timestring(
        updated_after, "updated_after"
    )
    updated_to = coerce_timestring(last_updated_to, "last-updated_to") or coerce_timestring(
        updated_before, "updated_before"
    )

    if (not source) and any([with_source_devices, with_source_assets]):
        raise ValueError("Can only include source assets/devices if 'source' parameter is provided.")

    series = ensure_sequence(series)
    aggregation_function = ensure_sequence(aggregation_function)
    params = (
        ("name", name),  # TODO, check if OData encoding works as expected
        ("fragmentType", fragment),
        ("source", source),
        ("bulkOperationId", bulk_id),
        ("dateFrom", date_from),
        ("dateTo", date_to),
        ("createdFrom", created_from),
        ("createdTo", created_to),
        ("lastUpdatedFrom", updated_from),
        ("lastUpdatedTo", updated_to),
        ("revert", encode(revert)),
        *(("series", s) for s in series),
        *(("aggregationFunction", f) for f in aggregation_function),
        *((k, encode(v)) for k, v in kwargs.items()),
    )
    return [(to_pascal_case(k), str(v)) for k, v in params if v is not None]


def expression_implies_order(expression: str | None) -> bool:
    """True if a raw expression/query string contains an ordering directive."""
    if not expression:
        return False
    return "revert" in expression or "orderby" in expression


def encode(value: Any | Sequence | None) -> Sequence | str | None:
    if value is None:
        return None
    if is_sequence(value):
        return tuple(encode(x) for x in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value  # TODO:   encode?
    raise ValueError(f"Unexpected value type '{type(value)}'. No idea how to encode.")


class JsonObject(dict):
    """Base class for JSON structures, wrapping standard dicts.

    This implementation features virtual `_json` and `_staged_json`
    attributes which enables use of the property helpers, as well as
    dot-notation read access via `[]` and `.get`.
    """

    @property
    def json(self) -> dict:
        return self

    @property
    def _staged_json(self) -> dict:
        return self

    # Need this wrapper to be able to deal with JsonObject
    # generically in CumulocityResource instances
    @classmethod
    def from_json(cls, json: dict, **_) -> Self:
        return cls(json)

    def __getitem__(self, path) -> Any:
        return get_by(self, path, fail=True)

    @overload
    def get(self, path: str) -> Any | None: ...
    @overload
    def get(self, path: str, default: T) -> Any | T: ...
    def get(self, path: str, default: Any = None) -> Any:
        return get_by(self, path, default=default)


class CumulocityObject(Mapping):
    """Base class for all Cumulocity database objects."""

    _meta: ResourceMeta

    def __init__(self, c8y: CumulocityRestClient | None = None, **kwargs):
        self.c8y = c8y
        self._source_json: dict = {}
        self._staged_json: dict = expand_dotted(kwargs)

    def __iter__(self):
        return iter(self.json)

    def __len__(self) -> int:
        return len(self.json)

    @property
    def json(self) -> dict:
        """Current JSON view: server-state merged with staged values."""
        if not self._staged_json:
            return self._source_json
        if not self._source_json:
            return self._staged_json
        return self._source_json | self._staged_json

    @property
    def resource_path(self) -> str:
        return self._meta.resource_path

    @property
    @abstractmethod
    def object_path(self) -> str:
        """Path to this specific object within Cumulocity."""

    def __repr__(self) -> str:
        return "".join(
            [  # -> ClassName(id=123, type=abc)
                type(self).__name__,
                "(",
                ", ".join(
                    [
                        f"{n}={getattr(self, n)}"
                        for n in ["id", "type"]
                        if hasattr(self, n) and getattr(self, n) is not None
                    ]
                ),
                ")",
            ]
        )

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

    def _rebuild(self, json: dict) -> None:
        # rebuild self to reflect different JSON
        self._source_json = json
        self._staged_json = {}

    def __contains__(self, path) -> bool:
        current = self.json
        for key in path.split("."):
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
        return path in self

    def __getitem__(self, path) -> Any:
        return get_by(self.json, path, fail=True)

    @overload
    def get(self, path: str) -> Any | None: ...
    @overload
    def get(self, path: str, default: T) -> Any | T: ...
    def get(self, path: str, default: Any = None) -> Any:
        return get_by(self.json, path, default=default)

    def _set(self, path: str, value: Any, fail: bool):
        keys = path.split(".")

        if len(keys) == 1:  # no path to drill down to -> direct assignment
            self._staged_json[path] = value
            return

        # copy the entire source branch to allow partial updates
        if keys[0] not in self._staged_json:
            staged = deepcopy(self._source_json.get(keys[0], {}))
        else:
            staged = self._staged_json[keys[0]]
        current = staged
        current_key = keys[0]

        for key in keys[1:-1]:
            if not isinstance(current, Mapping):
                if fail:
                    raise KeyError(f"Unable to access '{path}': '{current_key}' is not a dict")
                raise ValueError(f"Cannot set '{path}': '{current_key}' is not a dict")
            if key in current:
                current = current[key]
                current_key = key
                continue
            if fail:
                if to_pascal_case(key) in current:
                    raise KeyError(
                        f"Unable to access '{path}': '{key}' is missing — did you mean '{to_pascal_case(key)}'?"
                    )
                raise KeyError(f"Unable to access '{path}': '{key}' is missing")
            current[key] = {}
            current = current[key]
            current_key = key

        if not isinstance(current, Mapping):
            if fail:
                raise KeyError(f"Unable to access '{path}': '{current_key}' is not a dict")
            raise ValueError(f"Cannot set '{path}': '{current_key}' is not a dict")

        current[keys[-1]] = value
        self._staged_json[keys[0]] = staged

    def __setitem__(self, path, value):
        self._set(path, value, fail=True)

    def set(self, path, value):
        self._set(path, value, fail=False)

    def __iadd__(self, other) -> Self:
        for i in ensure_sequence(other):
            self._staged_json[i.name] = i.items
        return self

    def as_tuple(self, *paths: str | tuple[str, Any]) -> tuple:
        """Return selected field values as tuple.

        Args:
            paths (*str | tuple[str | Any]): Path-like expressions
                (dot-notation); each "expression" can be a tuple to specify
                a default value if path is not found, otherwise None is used.

        Returns:
            The extracted values (or defaults it specified) as tuple.
        """
        return as_tuple(self.json, list(paths))

    def as_record(self, **mapping: str | tuple[str | Any]) -> dict:
        """Return selected field values as dict.

        Args:
            mapping (**str | tuple[str | Any]): Mapping of result keys to
                path-like expressions (dot-notation); each "expression"
                can be a tuple to specify a default value if path is not
                found, otherwise None is used.

        Returns:
            The extracted values (or defaults it specified) as dictionary.
        """
        return as_record(self.json, mapping)

    async def _create(self, copy: bool = False, **params) -> Self:
        self._assert_c8y()
        object_json = await self.c8y.post(
                self.resource_path,
                json=self.json,
                params=map_params(**params) if params else (),
                accept=self._meta.object_mime_type,
            )
        if copy:
            return self._build(object_json, c8y=self.c8y)
        self._rebuild(object_json)
        return self

    async def _update(self, copy: bool = False) -> Self:
        # apply locally stages changes to the object
        return await self._apply(self._staged_json, copy=copy)

    async def _apply(self, json: dict, copy: bool = False) -> Self:
        # apply JSON fields as changes to the object
        self._assert_c8y()
        self._assert_key()
        object_json = await self.c8y.put(
            self.object_path,
            json=json,
            accept=self._meta.object_mime_type,
            content_type=self._meta.object_mime_type,
        )
        if copy:
            return self._build(object_json, c8y=self.c8y)
        self._rebuild(object_json)
        return self

    async def _delete(self, **params):
        self._assert_c8y()
        self._assert_key()
        await self.c8y.delete(self.object_path, params=params)

    async def _reload(self, copy: bool = False) -> Self:
        self._assert_c8y()
        self._assert_key()
        object_json = await self.c8y.get(
            self.object_path,
            accept=self._meta.object_mime_type,
        )
        if copy:
            return self._build(object_json, c8y=self.c8y)
        self._rebuild(object_json)
        return self

    async def delete(self, **_) -> None:  # allow override with parameters
        """Delete the object within the database."""
        await self._delete()

    def _assert_c8y(self):
        """Assert that a model object has a Cumulocity connection."""
        if not self.c8y:
            raise ValueError("Cumulocity connection reference must be set to allow direct database access.")

    @abstractmethod
    def _assert_key(self):
        """Assert that a model object has a database key."""


class WithId:
    """Mixin for objects with a simple database ID."""

    _source_json: dict  # declare only, this is defined in CumulocityObject
    _staged_json: dict  # declare only, this is defined in CumulocityObject
    _meta: ResourceMeta  # declare only, this is defined in CumulocityObject
    resource_path: str  # declare only, this is defined in CumulocityObject
    c8y: CumulocityRestClient | None  # declare only, this is defined in CumulocityObject
    _assert_c8y: Callable[[], None]  # declare only, this is defined in CumulocityObject
    _build: Callable[..., Self]  # declare only, this is defined in CumulocityObject

    @property
    def id(self):
        # id can never come from update
        return self._source_json.get("id", None)

    @property
    def object_path(self) -> str:
        return f"{self.resource_path}/{self.id}"

    def _assert_key(self):
        if not self.id:
            raise ValueError("The object ID must be set to allow direct object access.")

    async def _apply_to(self, other_id: str) -> Self:
        # apply locally staged changes to another object of the same kind
        self._assert_c8y()
        return self._build(
            json=await self.c8y.put(
                f"{self.resource_path}/{other_id}",
                json=self._staged_json,
                accept=self._meta.object_mime_type,
                content_type=self._meta.object_mime_type,
            ),
            c8y=self.c8y,
        )


class PageFetcher(Protocol):
    async def __call__(
        self, page: int, expression: str | None, params: Sequence[tuple[str, str]] | None, **_
    ) -> list: ...


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

    def build_object_path(self, object_id: str) -> str:
        """Build the path to a specific object of this resource.

        Args:
            object_id (int|str):  Cumulocity ID of the object

        Returns:
            The relative path to the object within Cumulocity.
        """
        return f"{self.resource_path}/{object_id}"

    async def _get(self, object_id: str, **kwargs) -> CO:
        return self._object_type.from_json(
            await self.c8y.get(
                self.build_object_path(object_id),
                params=map_params(**kwargs),
                accept=self._meta.object_mime_type,
            ),
            c8y=self.c8y,  # inject c8y instance
        )

    async def _get_last(
        self,
        expression: str | None,
        params: dict | Sequence[tuple[str, Any]] | None = None,
        as_values: str | Sequence[str | tuple[str, Any]] | None = None,
    ) -> CO | None:
        if expression:
            result_json = await self.c8y.get(
                f"{self.resource_path}?{expression}&currentPage=1&pageSize=1", accept=self._meta.object_mime_type
            )
        else:
            result_json = await self.c8y.get(self.resource_path, params=params, accept=self._meta.collection_mime_type)
        results = result_json[self._meta.collection_name]
        if not results:
            return None
        if as_values:
            return _extract_as_values(results[0], as_values)
        return self._object_type.from_json(results[0], c8y=self.c8y)

    async def _get_count(self, expression: str | None, params: Sequence[tuple[str, str]] | None) -> int:
        if expression:
            result_json = await self.c8y.get(f"{self.resource_path}?{expression}&pageSize=1&withTotalPages=true")
        else:
            # params are not merged, but we can be sure that page size etc. are not part of params
            result_json = await self.c8y.get(
                self.resource_path, params=(*params, ("pageSize", "1"), ("withTotalPages", "true"))
            )
        return result_json["statistics"]["totalPages"]

    async def _fetch_page(
        self, page: int, expression: str | None, params: Sequence[tuple[str, str]] | None, **_
    ) -> list:
        if expression:
            result = await self.c8y.get(f"{self.resource_path}?{expression}&currentPage={page}")
        else:
            result = await self.c8y.get(self.resource_path, params=(*(params or ()), ("currentPage", str(page))))
        return result[self._meta.collection_name]

    async def _iterate(
        self,
        *,
        expression: str | None = None,
        params: Sequence[tuple[str, str]] | None = None,
        page_number: int | None = None,
        limit: int | None = None,
        include: str | JsonMatcher | None = None,
        exclude: str | JsonMatcher | None = None,
        as_values: str | Sequence[str | tuple[str, Any]] | None = None,
        workers: int | None = None,
        preserve_order: bool = True,
        fetch_page: PageFetcher | None = None,
    ) -> AsyncIterator[CO]:
        current_page = page_number if page_number else 1
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

        _fetch = fetch_page or self._fetch_page
        # parallel fetching only applies when iterating across pages
        effective_workers = 1 if page_number else (workers or 1)
        stream = (
            self._stream_pages(_fetch, current_page, effective_workers, expression, params)
            if preserve_order or effective_workers <= 1
            else self._stream_pages_unordered(_fetch, current_page, effective_workers, expression, params)
        )

        async for obj_jsons in stream:
            if not obj_jsons:
                return
            if include or exclude:
                obj_jsons = [
                    x
                    for x in obj_jsons
                    if (not include or include.safe_matches(x)) and (not exclude or not exclude.safe_matches(x))
                ]
            for json in obj_jsons:
                if as_values:
                    yield _extract_as_values(json, as_values)
                else:
                    yield self._object_type.from_json(json, c8y=self.c8y)
                num_results += 1
                # exit as soon as the limit is satisfied, even if that lands
                # exactly on a page's last item - no need to fetch another
                # page just to confirm there's nothing more
                if limit and num_results >= limit:
                    return
            if page_number:
                return

    async def _stream_pages(
        self,
        fetch: "PageFetcher",
        start_page: int,
        workers: int,
        expression: str | None,
        params: Sequence[tuple[str, str]] | None,
    ) -> AsyncIterator[list]:
        """Yield pages in launch order.

        When `workers > 1`, keeps a sliding window of `workers` concurrent
        page-fetch tasks: as soon as the head completes (and is yielded), a
        new fetch is launched, so workers stay continuously busy without
        sacrificing page ordering. Stops on the first empty page; any pages
        launched speculatively past it are cancelled.
        """
        current = start_page

        if workers <= 1:
            while True:
                page = await fetch(current, expression=expression, params=params)
                yield page
                if not page:
                    return
                current += 1

        in_flight: "deque[asyncio.Task]" = deque()

        def launch():
            nonlocal current
            in_flight.append(asyncio.create_task(fetch(current, expression=expression, params=params)))
            current += 1

        try:
            for _ in range(workers):
                launch()
            while in_flight:
                page = await in_flight.popleft()
                yield page
                if not page:
                    return
                launch()
        finally:
            for t in in_flight:
                t.cancel()
            for t in list(in_flight):
                try:
                    await t
                except BaseException:  # noqa: BLE001
                    pass

    async def _stream_pages_unordered(
        self,
        fetch: "PageFetcher",
        start_page: int,
        workers: int,
        expression: str | None,
        params: Sequence[tuple[str, str]] | None,
    ) -> AsyncIterator[list]:
        """Yield pages as they complete — no ordering guarantee.

        Same sliding window as `_stream_pages`, but yields whichever fetch
        finishes first. Use when the caller will sort results downstream
        (or doesn't care about order).

        Termination: once any in-flight task returns an empty page, stop
        launching new fetches. The remaining batch is fully drained — valid
        pages from the same completion batch are still yielded — and any
        tasks still pending after that are cancelled by `finally`. Up to
        `workers` speculative requests may have been launched past
        end-of-data; their results are discarded.
        """
        current = start_page
        in_flight: set[asyncio.Task] = set()
        stop_launching = False

        def launch():
            nonlocal current
            in_flight.add(asyncio.create_task(fetch(current, expression=expression, params=params)))
            current += 1

        try:
            for _ in range(workers):
                launch()
            while in_flight:
                done, _pending = await asyncio.wait(in_flight, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    in_flight.discard(task)
                    page = task.result()
                    if not page:
                        stop_launching = True
                    else:
                        yield page
                if not stop_launching:
                    for _ in done:
                        launch()
        finally:
            for t in in_flight:
                t.cancel()
            for t in list(in_flight):
                try:
                    await t
                except BaseException:  # noqa: BLE001
                    pass

    async def to_dataframe(
        self,
        *args,
        columns: Sequence[str | tuple[str, str]],
        workers: int = 5,
        **kwargs,
    ):
        """Bulk-load matching objects into a Pandas DataFrame.

        Streams pages concurrently (sliding window, `workers` in flight) and
        appends each object's values directly into per-column lists — no
        intermediate row tuples, no transposition. The fetch order is
        unordered unless the underlying `select(...)` enforces ordering via
        its arguments (e.g. `asc=True`, `order_by=...`); for typical
        bulk loads where sorting happens downstream this gives maximum
        throughput.

        Args:
            *args: Positional args forwarded to `select(...)`.
            columns: Sequence of column specs. Each entry is either a bare
                JSON path (used as both column name and access path) or a
                `(name, path)` tuple.
            workers: Number of concurrent page fetches; default 5.
            **kwargs: Keyword args forwarded to `select(...)`.

        Returns:
            A Pandas DataFrame; one column per spec, one row per matching
            object.
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError("pandas is required. Install with: pip install pyc8y[pandas]") from e
        if not hasattr(self, "select"):
            raise NotImplementedError(f"{type(self).__name__} does not implement select(...)")

        names = [c if isinstance(c, str) else c[0] for c in columns]
        paths = [c if isinstance(c, str) else c[1] for c in columns]
        col_data: dict[str, list] = {n: [] for n in names}

        select = getattr(self, "select")
        async for obj in select(*args, workers=workers, **kwargs):
            for name, path in zip(names, paths):
                col_data[name].append(obj.get(path))
        return pd.DataFrame(col_data)

    async def _create(self, *objects: CO, workers: int | None = None) -> None:
        await run_batched(
            objects, workers, lambda x: self.c8y.post(self.resource_path, json=x.json, accept=None)
        )

    async def _create_bulk(
        self,
        *objects: CO,
        path: str | None = None,
        batch_size: int | None = None,
        workers: int | None = None,
    ) -> None:
        target = path or self.resource_path
        chunks = (
            [objects] if not batch_size
            else [objects[i : i + batch_size] for i in range(0, len(objects), batch_size)]
        )

        async def post_chunk(chunk: Sequence[CO]) -> None:
            await self.c8y.post(
                target,
                json={self._meta.collection_name: [o.json for o in chunk]},
                content_type=self.collection_mime_type,
            )

        await run_batched(chunks, workers, post_chunk)

    async def _update(self, *objects: CO, workers: int | None = None) -> None:
        await run_batched(
            objects,
            workers,
            lambda x: self.c8y.put(self.build_object_path(x.id), json=x._staged_json, accept=None),
        )

    async def _apply_to(self, model: dict | CO, *objects: str | CO, workers: int | None = None) -> None:
        model_json = model if isinstance(model, dict) else model._staged_json
        await run_batched(
            ensure_ids(objects),
            workers,
            lambda x: self.c8y.put(
                self.build_object_path(x), json=model_json, content_type=self._meta.object_mime_type, accept=None
            ),
        )

    # this one should be ok for all implementations, hence we define it here
    async def _delete(self, *objects: str | CO, workers: int | None = None) -> None:
        await run_batched(
            ensure_ids(objects),
            workers,
            lambda x: self.c8y.delete(self.build_object_path(x)),
        )


def skim_latest_by(items: Sequence[T], key: Callable[[T], Any]) -> dict[Any, T]:
    """Reduce a list of items ordered newest-first to the first (i.e.
    latest) occurrence of each `key(item)` value.

    Items for which `key` returns None are skipped.
    """
    latest: dict[Any, T] = {}
    for item in items:
        k = key(item)
        if k is not None and k not in latest:
            latest[k] = item
    return latest


def resolve_page_size(
    page_size: int | None,
    limit: int | None,
    include: object | None = None,
    exclude: object | None = None,
) -> int:
    """Resolve the effective page size for a paged query.

    If the caller passed an explicit `page_size`, use it as-is. Otherwise:
    - When `limit` is set AND no client-side filter (`include`/`exclude`) is in
      play, match `page_size` to `limit` so we page once and return.
    - Otherwise use `DEFAULT_PAGE_SIZE`.
    """
    if page_size is not None:
        return page_size
    has_filter = include is not None or exclude is not None
    return limit if (limit is not None and not has_filter) else DEFAULT_PAGE_SIZE


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
