The **pyc8y** module's main API classes provide access to various contexts
within the Cumulocity REST API. Use it to read existing data or modify in
bulk.

See also the [Object model](docs-model.md) section for object creation and
object-oriented access in general.

## Querying the database

The main API classes can be used to read individual objects by their
respective key, usually the Cumulocity object ID:

```python
some_object = await c8y.inventory.get("123456")
some_user = await c8y.users.get("mini_me")
some_id = await c8y.identity.get("9876543210", "c8y_Serial")
```

To access entire collections most APIs provide convenient query functions
which reflect the respective API's capabilities:

```python
objects = await c8y.inventory.get_all(name="My*", limit=10)
```

The `get_all` function provides the query results as a list, the
feature-equivalent `select` function works as a generator for streaming
access. Both functions perform automatic paging if necessary.

The returned objects are instances of the [Object model](docs-model.md) and the
functions are properly typed, so the results can conveniently used 
directly as-is:

```python
async for event in c8y.events.select(source="123456", max_age="1d", limit=100):
    print(f"Event: #{event.id} {event.time}, Type {event.type}")
```

### Flexible query parameters

While all query functions are functionally equivalent, each API provides a
specialized version which reflects the respective REST API's capabilities.
For example, the _Inventory API_ provides OData-like queries which for
example are not supported for the _Event API_ or _Operation API_.

```python
objects = await c8y.inventory.get_all(query="name eq 'My*'", limit=10)
```

All potential filters available through code completion. They match the
REST API's naming and function - however, the names have been renamed to
match Python's _snake_case_ naming convention (e.g. `date_from` instead
of `dateFrom`). The original names can always be used as a fallback, though.
Additionally, convenient alternatives are provided for date-like query
parameters:

```python
c8y.events.get_all(source="123456", dateFrom="2025-01-01")  # original
c8y.events.get_all(source="123456", date_from="2025-01-01")  # Pythonic
c8y.events.get_all(source="123456", after="2025-01-01")  # alternative
c8y.events.get_all(source="123456", max_age="1d")  # convenience helper
```
All date-like parameters accept timezone-aware `datetime` objects, ISO
date/time strings as well as `"now"` as a convenience alternative.

As a fallback, all query functions support the direct definition of a
REST API expression:

```python
# knowing it better
c8y.inventory.get_all("q=$filter=name eq 'M01' $orderby=lastUpdated")
```

## High-performance throughput

The SDK features an _async first_ design with IO concurrency and high
throughput in mind. Hence, all query functions can be executed in
_concurrent_ mode via the `workers` parameter:

```python
all_devices = await c8y.device_inventory.get_all(limit=None, page_size=100, workers=20)
```

This will internally fetch pages concurrently and return the complete
set. Results will be returned in random order (by completion), unless
an ordering parameter is specified:

```python
all_events = await c8y.events.get_all(
    source="12345",
    ascending=True,  # or: revert=True
    limit=None,
    page_size=100,
    workers=20)
```

Especially when working on large data sets, the full result object's
JSON is usually obsolete. To directly forfeit the JSON data and only
process relevant fields, the `as_values` parameter can be used on all
query functions: 

```python
async for values in c8y.inventory.select(
        type="MyDevice",
        as_values=("id", ("name", "undefined"), "lastUpdated")):
    print(f"#{values[0]} '{values[1]}', last updated: {values[2]}")
```

## Object manipulation and bulk processing

The main API classes can also be used to directly manipulate the database
without the need to pull object instances:

```python
# add a new fragment to a known set of inventory objects:
new_fragment_json = {"my_AdditionalFragment": {"essential": True}}
await c8y.inventory.update(new_fragment_json, "123456", "1238957", "12399192")
```

Similar functions exist to `create` and `delete` objects in bulk. Each API
class additionally provides access to API specific functionality, for example
to assign group memberships, define child devices, reset user passwords, ...

Like the query functions, all bulk operations feature a `workers` parameter to
enable concurrency and maximize throughput:

```python
many_ids = [...]
await c8y.inventory.delete(*many_ids, workers=20)
```

Because all these functions are defined as async, the bulk operations can 
easily be combined using standard `asyncio` means:

```python
# clean up my data
object_events = await c8y.events.get_all(source=my_object.id, limit=None, workers=20, as_values="id")
object_alarms = await c8y.alarms.get_all(source=my_object.id, limit=None, workers=20, as_values="id")
await asyncio.gather(
    c8y.events.delete( *object_events, workers=20),
    c8y.alarms.delete(*object_alarms, workers=20),
)
await c8y.inventory.delete(my_object.id)
```
