# Copyright (c) 2026 Christoph Souris

import jmespath as jmespath_lib

from pyc8y.model.matcher import JsonMatcher


class JmesPathMatcher(JsonMatcher):
    """JsonMatcher implementation for JMESPath."""

    def __init__(self, expression: str, warn_on_error: bool = True):
        super().__init__(expression, warn_on_error)
        self.compiled_expression = jmespath_lib.compile(expression)

    def matches(self, json: dict) -> bool:
        # pylint: disable=broad-exception-caught
        return self.compiled_expression.search(json)


def jmespath(expression: str) -> JmesPathMatcher:
    """Create a JMESPathMatcher from an expression."""
    return JmesPathMatcher(expression)
