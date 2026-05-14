# Copyright (c) 2026 Christoph Souris

import re
from typing import Sequence, Any


def is_sequence(obj: Any) -> bool:
    """Determine if an object is a sequence, i.e. list or tuple."""
    return isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray))


def ensure_sequence(obj: Any | Sequence[Any] | None) -> Sequence[Any]:
    """Ensure a sequence: pass sequences through, wrap scalars in a 1-tuple,
    and map None to an empty tuple."""
    if obj is None:
        return ()
    return obj if is_sequence(obj) else (obj,)


def unwrap_args(args: Sequence[Any]) -> tuple[Any, ...]:
    """Unwrap a *args-style argument tuple, flattening one level of sequences.

    Supports the stdlib min/max calling convention: callers may pass items
    either as individual positional arguments or collected in sequences, and
    the two forms can be mixed.

    Examples:
        unwrap_args(("a", "b"))         -> ("a", "b")
        unwrap_args((["a", "b"],))      -> ("a", "b")
        unwrap_args((["a", "b"], "c"))  -> ("a", "b", "c")
    """
    result: list = []
    for item in args:
        if is_sequence(item):
            result.extend(item)
        else:
            result.append(item)
    return tuple(result)


def first(*values: Any) -> Any | None:
    """Returns the first defined (not None) value in a sequence of
    candidates.

    Args:
        values (*Any): A sequence of (potential) values.

    Returns:
        The first non-None value or None if all are None.
    """
    return next((x for x in values if x is not None), None)


def concat(*strings: str | None):
    """Concatenate non-None strings."""
    return "".join(x for x in strings if x)


def concat_with(sep: str, *strings: str | None):
    """Concatenate non-None strings with separator."""
    return sep.join(x for x in strings if x)


def like(expression: str, string: str):
    """Check if like-expression matches a string.

    Only supports * at beginning and end.
    """
    return (
        expression[1:-1] in string
        if expression.startswith("*") and expression.endswith("*")
        else (
            string.startswith(expression[:-1])
            if expression.endswith("*")
            else string.endswith(expression[1:]) if expression.startswith("*") else expression == string
        )
    )


def matches(expression: str, string: str):
    """Check if regex expression matches a string."""
    try:
        return re.search(expression, string) is not None
    except re.error:
        return False


def encode_odata_query_value(value):
    """Encode value strings according to OData query rules.
    http://docs.oasis-open.org/odata/odata/v4.01/odata-v4.01-part2-url-conventions.html#sec_URLParsing
    http://docs.oasis-open.org/odata/odata/v4.01/cs01/abnf/odata-abnf-construction-rules.txt"""
    # single quotes escaped through single quote
    return re.sub("'", "''", value)


def encode_odata_text_value(value):
    """Encode value strings according to OData query rules.
    http://docs.oasis-open.org/odata/odata/v4.01/odata-v4.01-part2-url-conventions.html#sec_URLParsing
    http://docs.oasis-open.org/odata/odata/v4.01/cs01/abnf/odata-abnf-construction-rules.txt"""
    # single quotes escaped through single quote
    encoded_quotes = re.sub("'", "''", value)
    return encoded_quotes if " " not in encoded_quotes else f"'{encoded_quotes}'"
