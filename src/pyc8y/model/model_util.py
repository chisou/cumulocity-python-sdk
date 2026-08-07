# Copyright (c) 2026 Christoph Souris

import re
from datetime import datetime, timezone, timedelta, date
from typing import Any


def coerce_datetime(value: str | datetime | None, name: str | None = None) -> datetime | None:
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
        datetime_value = to_datetime(value)
        if datetime_value.tzinfo is None:
            datetime_value = datetime_value.replace(tzinfo=timezone.utc)
        return datetime_value
    except ValueError:
        raise ValueError(f"Unable to convert to datetime{param_name()}.")


# TODO: Bit unelegant that it might return None, no? Small if around for each invocation?
def coerce_timedelta(value: str | timedelta | None, name: str | None = None) -> timedelta | None:
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
        except ValueError:
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


def coerce_timestring(value: str | datetime | date | None, name: str | None = None) -> str | None:
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
    if isinstance(value, date):
        return to_timestring(value)
    if value == "now":
        return now_timestring()
    if value == "today":
        return now_timestring()
    try:
        value = to_datetime(value)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
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


def get_by(dictionary: dict, path: str, default: Any = None, fail: bool = False) -> Any:
    """Select a nested value from a dictionary by path-like expression
    (dot notation).

    Args:
        dictionary (dict):  the dictionary to extract values from
        path (str):  a path-like expressions
        default (Any):  default value to return if the path expression
            doesn't match a value in the dictionary.
        fail (bool):  whether to raise an exception if the path expression
            doesn't match a value in the dictionary.

    Returns:
        The extracted value or the specified default.
    """
    keys = path.split(".")
    current = dictionary

    for key in keys:
        if not isinstance(current, dict):
            return default
        if key in current:
            current = dict.__getitem__(current, key)
            continue
        pascal_key = to_pascal_case(key)
        if pascal_key in current:
            current = dict.__getitem__(current, pascal_key)
            continue
        if fail:
            raise KeyError(f"Unable to find '{path}' in object JSON.")
        return default

    return current


def as_tuple(data: dict, paths: list[str | tuple]) -> tuple:
    """Select nested values from a dictionary by path-like expressions
    (dot notation) and return as tuple.

    Args:
        data (dict):  the dictionary to extract values from
        paths: (list):  a list of path-like expressions; each "expression"
            can be a tuple to define a default value other than None.

    Returns:
        The extracted values (or defaults it specified) as tuple. The
        number of elements in the tuple matches the length of the `paths`
        argument.
    """
    return tuple(
        get_by(data, path[0] if isinstance(path, tuple) else path, path[1] if isinstance(path, tuple) else None)
        for path in paths
    )


def as_record(data: dict, mapping: dict[str, str | tuple[str | Any]]) -> dict:
    """Select nested values from a dictionary by path-like expressions
    (dot notation) and return as record (dict).

    Args:
        data (dict):  the dictionary to extract values from
        mapping: (dict):  a dictionary mapping result keys to a path-like
            expression; each "expression" can be a tuple to define a
            default value other than None.

    Returns:
        The extracted values (or defaults it specified) as dictionary.
    """
    return {
        key: get_by(data, path[0] if isinstance(path, tuple) else path, path[1] if isinstance(path, tuple) else None)
        for key, path in mapping.items()
    }


def to_datetime(value: str) -> datetime:
    """Convert a Cumulocity datetime object to a datetime."""
    return datetime.fromisoformat(value)


def to_timestring(value: datetime | date) -> str:
    """Convert a Cumulocity timestring object to a string."""
    if isinstance(value, datetime):
        return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return value.isoformat()


def now_datetime():
    """Provide the current time as datetime object."""
    return datetime.now(timezone.utc)


def now_timestring() -> str:
    """Provide an ISO timestring for the current time."""
    return datetime.now(timezone.utc).isoformat()


def today_timestring() -> str:
    """Provide an ISO timestring for the current date."""
    return date.today().isoformat()


def to_pascal_case(name: str) -> str:
    """Convert a given `snake_case` (default Python style) name to `pascalCase`
    (default for names in Cumulocity)"""
    parts = list(filter(None, name.split("_")))
    if len(parts) == 1:
        return name
    return parts[0] + "".join([x.title() for x in parts[1:]])
