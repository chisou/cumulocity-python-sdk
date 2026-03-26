import pytest

from pyc8y.auth import BasicAuth
from pyc8y.client import CumulocityRestClient



@pytest.fixture(name="c8y_httpbin")
async def fix_httpbin():
    return CumulocityRestClient("https://httpbin.org", tenant_id="", auth=BasicAuth("user", "auth"))



@pytest.mark.parametrize("method, json, accept, content_type", [
    ("GET", None, None, None),
    ("GET", None, "text/plain", None),
    ("POST", {"a":1}, None, None),
    ("POST", {"a":1}, "text/plain", "text/plain"),
    ("PUT", {"a":1}, None, None),
    ("PUT", {"a":1}, "text/plain", "text/plain"),
])
@pytest.mark.asyncio
async def test_session_headers(c8y_httpbin, method, json, accept, content_type):
    """Ensure that session headers are merged with request headers."""

    c8y = c8y_httpbin
    result = await c8y.request(method, "/anything", accept=accept, content_type=content_type)
    # -> there is always an Authorization header
    assert "Authorization" in result["headers"]
    # -> there is always an Accept header
    assert result["headers"]["Accept"] == (accept or "application/json")
    # -> body defines whether there is a Content-Type header
    if json:
        assert result["headers"]["Content-Type"] == (content_type or "application/octet-stream")
    else:
        assert "Content-Type" not in result["headers"]

    await c8y.request(method, "/anything", accept=accept, content_type=content_type)

