# Copyright (c) 2026 Christoph Souris

import logging
import ssl
from collections import Counter
from enum import StrEnum
from typing import Self

import aiohttp
import certifi
import orjson

from pyc8y.auth import Auth


logger = logging.getLogger(__name__)


def loggable_params(params):
    """Provide a log-friendly formatted string of HTTP parameters."""
    if not params:
        return '-'
    return ', '.join(f"{k}={v}" for k, v in params.items())


class ProcessingMode(StrEnum):
    """Cumulocity REST API processing modes."""
    PERSISTENT = 'PERSISTENT'
    TRANSIENT = 'TRANSIENT'
    QUIESCENT = 'QUIESCENT'


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class HttpError(Exception):
    """Base class for technical HTTP errors."""
    def __init__(self, method: str, url: str, code: int, message: str):
        super().__init__(f'HTTP {code}: {method} {url} - {message}')
        self.method = method
        self.url = url
        self.code = code
        self.message = message


class UnauthorizedError(HttpError):
    """Error raised for unauthorized access."""
    def __init__(self, method: str, url: str = None, message: str = "Unauthorized."):
        super().__init__(method, url, 401, message)


class MissingTfaError(UnauthorizedError):
    """Error raised for unauthorized access."""
    def __init__(self, method: str, url: str = None, message: str = "Missing TFA Token."):
        super().__init__(method, url, message)


class AccessDeniedError(HttpError):
    """Error raised for denied access."""
    def __init__(self, method: str, url: str = None, message: str = "Access denied."):
        super().__init__(method, url, 403, message)


class BatchError(Exception):
    """Error raised after a batch processing."""
    def __init__(self, errors: list[Exception]):
        super().__init__(self._build_message(errors))
        self.errors = errors

    @staticmethod
    def _build_message(errors) -> str:
        counts = Counter(type(e).__name__ for e in errors)
        parts = [
            f"{name}({count})" if count > 1 else name
            for name, count in counts.items()
        ]
        return f"Batch processing raised {len(errors)} errors: {', '.join(parts)}"


class CumulocityRestApi(object):

    def __init__(
            self,
            base_url: str,
            tenant_id: str,
            auth: Auth,
            application_key: str = None,
            processing_mode: str = None
    ):
        self.base_url = base_url.rstrip('/') + '/'
        self.tenant_id = tenant_id
        self.auth = auth
        self.application_key = application_key
        self.processing_mode = processing_mode
        self._session = None

    async def __aenter__(self) -> Self:
        _ = await self.session  # ensure session is created
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    @property
    async def session(self) -> aiohttp.ClientSession:
        if not self._session:
            # ensure certifi-based SSL verification
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            # initialize default session parameters
            headers = {
                "Authorization": self.auth.build_auth_header(),
                "Accept": "application/json",  # default, can be overridden per request
            }
            if self.application_key:
                headers["X-Cumulocity-Application-Key"] = self.application_key
            if self.processing_mode:
                headers["X-Cumulocity-Processing-Mode"] = self.processing_mode
            # create session
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=ssl_context),
                base_url=self.base_url,
                headers=headers,
            )
            return self._session
        return self._session

    @property
    def  username(self):
        return self.auth.get_username()

    async def request(
            self,
            method: str,
            resource: str,
            params: dict = None,
            json: dict = None,
            accept: str | None = "application/json",
            content_type: str = None,  # application/json is assumed/automatically inserted if there is content
    ) -> dict:
        """Perform an HTTP request.

        Args:
            method(str): The HTTP method to use.
            resource(str): The resource path.
            params (dict): Additional request parameters
            json (dict): JSON body (nested dict)
            accept(str): Accept header value; `application/json` is assumed/automatically inserted if None
            content_type(str): Content-Type header value; `application/json` is assumed/automatically inserted
                if `json` is provided.

        Returns:
            The JSON response (nested dict), {} if no response body is returned.

        Raises:
            KeyError:  if the resources is not found (404)
            ValueError:  if the request cannot be processes (5xx) or cannot be processed for other reasons
                (only 2xx is accepted).
        """
        if json is not None:
            content_type = content_type or "application/json"
        session = await self.session
        async with session.request(
                method=method,
                url=resource,
                params=params,
                data=orjson.dumps(json) if json else None,
                headers={k: v for k, v in {"Accept": accept, "Content-Type": content_type}.items() if v}
        ) as r:
            logger.debug(
                "%s %s %s %s %s",
                method,
                r.status,
                resource,
                "-" if not params else ", ".join(f"{k}={v}" for k, v in params.items()),
                "-" if not json else orjson.dumps(json),
            )
            if r.status == 401:
                raise UnauthorizedError(method, resource, message=(await r.json())['message'])
            if r.status == 403:
                raise AccessDeniedError(method, resource, message=(await r.json())['message'])
            if r.status == 404:
                raise KeyError(f"No such object: {resource}")
            if 500 <= r.status <= 599:
                raise ValueError(f"Invalid {method} request. Status: {r.status}, Response:\n {await r.text()}")
            if r.status not in (200, 201, 204):
                raise ValueError(f"Unable to perform {method} request. Status: {r.status}, Response:\n {await r.text()}")
            if r.status in (200, 201):
                return orjson.loads(await r.read())
            return {}

    async def get(self, resource: str, params: dict = None, accept: str = None) -> dict:
        return await self.request("GET", resource, params, None, accept=accept)

    async def post(self, resource: str, json: dict, accept: str = None, content_type: str = None) -> dict:
        return await self.request("POST", resource, None, json, accept=accept, content_type=content_type)

    async def put(self, resource: str, json: dict, params: dict = None, accept: str = None, content_type: str = None) -> dict:
        return await self.request("PUT", resource, params, json, accept=accept, content_type=content_type)

    async def delete(self, resource: str, params: dict = None) -> dict:
        return await self.request("DELETE", resource, params)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
