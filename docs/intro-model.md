The **Cumulocity Python SDK**'s object model provides object-oriented
access to the Cumulocity REST API. Use it to create and modify single
objects within the Database.

### Object-oriented database access

The object model define functions for direct, object-oriented database access:

```Python
# Create an object in the database and use it
obj = ManagedObject(
    connection,
    name="MyObject",
    type="my_CustomType"
)
obj = await obj.create()

# Update the object and write changes to the database
obj.type = "my_ChangedType"  
await obj.update()

# Remove the previously created object from the database
await obj.delete()
```

Note: These objects can also be used directly within the
[Main API classes](docs-main.md) to modify data in bulk.

### Direct JSON data access

The object model instances are essentially enriched JSON-like objects and
can be used like standard nested dictionaries:

```python
the_value = obj["my_Fragment"]["value"]  # read nested value
obj["my_Fragment"]["value"] = new_value  # set nested value
```

For convenience the SDK supports dot-notation for the `[]` operator:

```python
the_value = obj["my_Fragment.value"]  # read nested value
obj["my_Fragment.value"] = new_Value  # set nested value
```

Likewise, the `.get` and `.set` functions:

```python
the_value = obj.get("my_Fragment.value", default=42)  # read nested value
obj.set("my_Fragment.value", 42)  # set a nested value
```

which also protect against missing keys _along the path_. 

Many Cumulocity objects define _standard_ properties, e.g. `id`, `type`, 
`name` and `creationTime`. These fields can _additionally_ also read
(and set if allowed) through explicit class properties:

```python
# Most objects have an id, name, and type
print(f"Object details: #{obj.id}, '{obj.name}' ({obj.type})")

# Date-like properties can be read as strings (actual JSON value) or datetime (parsed)
total_minutes = int((datetime.now(timezone.utc) - obj.creation_datetime).total_seconds() / 60)
print(f"Object creation: {obj.creation_time} ({total_minutes} minutes ago)")
```

These properties use Pythonic `snake_case` naming to integrate nicely into
Python code. The original data is always available through direct access,
e.g. `obj["creationTime"]`.



