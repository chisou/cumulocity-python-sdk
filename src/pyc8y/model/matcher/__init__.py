# Copyright (c) 2026 Christoph Souris

from ._matcher import (
    JsonMatcher,
    AllMatcher,
    match_all,
    AnyMatcher,
    match_any,
    NotMatcher,
    match_not,
    FragmentMatcher,
    fragment,
    FieldMatcher,
    field,
    DescriptionMatcher,
    description,
    TextMatcher,
    text,
    CommandMatcher,
    command,
)

try:
    import pydictdisplayfilter as _pydf
    from ._pydf import PydfMatcher, pydf
except ImportError as e:
    pass

try:
    import jmespath as _jmespath
    from ._jmespath import JmesPathMatcher, jmespath
except ImportError:
    pass

try:
    import jsonpath_ng as _jsonpath_ng
    from ._jsonpath import JsonPathMatcher, jsonpath
except ImportError:
    pass
