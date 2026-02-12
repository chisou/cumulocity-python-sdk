# Copyright (c) 2026 Christoph Souris

import re
from typing import Sequence, Any


def is_sequence(obj: Any) -> bool:
    """Determine if an object is a sequence, i.e. list or tuple."""
    return isinstance(obj, Sequence) and not isinstance(obj, (str, bytes))


def flatten(items: list[list | tuple] | list | tuple) -> tuple:
    """Ensure a flat list.

    Args:
        items (list | tuple): A list or list of lists of items.

    Returns:
        Tuple of the list items.
    """
    if len(items) == 1 and isinstance(items[0], (list, tuple)):
        return tuple(items[0])
    return tuple(items)  # always tuple for consistency


def concat(*strings: str | None):
    """Concatenate non-None strings."""
    return ''.join(x for x in strings if x)


def concat_with(sep: str, *strings: str | None):
    """Concatenate non-None strings with separator."""
    return sep.join(x for x in strings if x)


def like(expression: str, string: str):
    """Check if like-expression matches a string.

    Only supports * at beginning and end.
    """
    return (
        expression[1:-1] in string if expression.startswith('*') and expression.endswith('*')
        else string.startswith(expression[:-1]) if expression.endswith('*')
        else string.endswith(expression[1:]) if expression.startswith('*')
        else expression == string
    )


def matches(expression: str, string: str):
    """Check if regex expression matches a string."""
    try:
        return re.search(expression, string) is not None
    except re.error:
        return False


def sanitize_page_size(limit: int, page_size: int) -> int:
    """Harmonize/sanitize page_size for a database query.

    The page size should never exceed the given limit of a query. Hence,
    this function sets the page size to the limit if undefined or too large.
    A smaller page size passes as this can be a performance consideration.

    Returns:
        Updated page size.
    """
    return min(limit or 1001, page_size or 1001, 1000)


def encode_odata_query_value(value):
    """Encode value strings according to OData query rules.
    http://docs.oasis-open.org/odata/odata/v4.01/odata-v4.01-part2-url-conventions.html#sec_URLParsing
    http://docs.oasis-open.org/odata/odata/v4.01/cs01/abnf/odata-abnf-construction-rules.txt """
    # single quotes escaped through single quote
    return re.sub('\'', '\'\'', value)


def encode_odata_text_value(value):
    """Encode value strings according to OData query rules.
    http://docs.oasis-open.org/odata/odata/v4.01/odata-v4.01-part2-url-conventions.html#sec_URLParsing
    http://docs.oasis-open.org/odata/odata/v4.01/cs01/abnf/odata-abnf-construction-rules.txt """
    # single quotes escaped through single quote
    encoded_quotes = re.sub('\'', '\'\'', value)
    return encoded_quotes if " " not in encoded_quotes else f"'{encoded_quotes}'"