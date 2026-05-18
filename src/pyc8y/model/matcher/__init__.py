# Copyright (c) 2026 Christoph Souris

from ._matcher import (
    JsonMatcher as JsonMatcher,
    AllMatcher as AllMatcher,
    match_all as match_all,
    AnyMatcher as AnyMatcher,
    match_any as match_any,
    NotMatcher as NotMatcher,
    match_not as match_not,
    FragmentMatcher as FragmentMatcher,
    fragment as fragment,
    FieldMatcher as FieldMatcher,
    field as field,
    DescriptionMatcher as DescriptionMatcher,
    description as description,
    TextMatcher as TextMatcher,
    text as text,
    CommandMatcher as CommandMatcher,
    command as command,
)

try:
    from ._pydf import PydfMatcher as PydfMatcher, pydf as pydf
except ImportError:
    pass

try:
    from ._jmespath import JmesPathMatcher as JmesPathMatcher, jmespath as jmespath
except ImportError:
    pass

try:
    from ._jsonpath import JsonPathMatcher as JsonPathMatcher, jsonpath as jsonpath
except ImportError:
    pass
