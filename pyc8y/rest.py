# Copyright (c) 2026 Christoph Souris

import logging
import os
import ssl
from collections import Counter
from enum import StrEnum
from pathlib import Path
from typing import Self, Sequence, Any

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
    def __init__(self, method: str, url: str = None, message: str | None = "Unauthorized."):
        super().__init__(method, url, 401, message)


class MissingTfaError(UnauthorizedError):
    """Error raised for unauthorized access."""
    def __init__(self, method: str, url: str = None, message: str | None = "Missing TFA Token."):
        super().__init__(method, url, message)


class AccessDeniedError(HttpError):
    """Error raised for denied access."""
    def __init__(self, method: str, url: str = None, message: str | None = "Access denied."):
        super().__init__(method, url, 403, message)


class BatchError(Exception):
    """Error raised after a batch processing."""
    def __init__(self, errors: list[BaseException]):
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


class CumulocityRestClient(object):

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

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    @property
    async def session(self) -> aiohttp.ClientSession:
        if not self._session:
            # ensure certifi-based SSL verification
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            # initialize default session parameters
            headers = {
                "Authorization": self.auth.build_auth_header(),
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

    @classmethod
    async def authenticate(
            cls,
            base_url: str,
            tenant_id: str,
            username: str,
            password: str,
            tfa_token: str = None,
    ) -> (str, str):
        """Authenticate a user using OAI Secure login method.

        Args:
            base_url (str):  Cumulocity base URL, e.g. https://cumulocity.com
            tenant_id (str):  The ID of the tenant to connect to
            username (str):  Username
            password (str):  User password
            tfa_token (str):  Currently valid two-factor authorization token

        Returns:
            A string tuple of JWT auth token and corresponding XRSF token.
        """
        url = f'{base_url.rstrip("/")}/tenant/oauth?tenant_id={tenant_id}'
        form_data = {'grant_type': 'PASSWORD', 'username': username, 'password': password, 'tfa_token': tfa_token}
        async with aiohttp.ClientSession() as session:
            async with session.post(url=url, data=form_data, timeout=60.0) as response:
                response_json = orjson.loads(await response.text() or "") or {}
                if response.status == 401:
                    response_json = orjson.loads(await response.text()) or {}
                    message = response_json.get("message", None)
                    # 1st request might fail due to missing TFA code
                    if any(x in message for x in ['TOTP', 'TFA']):
                        raise MissingTfaError(HttpMethod.POST, str(response.url), message)
                    raise UnauthorizedError(HttpMethod.POST, str(response.url), message)
                if response.status != 200:
                    message = response_json.get("message", "Invalid request!")
                    raise HttpError(HttpMethod.POST, str(response.url), response.status, message)
                return response.cookies['authorization'], response.cookies['XSRF-TOKEN']

    async def request(
            self,
            method: str,
            resource: str,
            params: tuple[str, Any] | dict | None = None,
            json: dict | None = None,
            accept: str | None = "application/json",
            content_type: str | None = None,
    ) -> dict:
        """Perform an HTTP request.

        Args:
            method(str): The HTTP method to use.
            resource(str): The resource path.
            params (dict): Additional request parameters
            json (dict): JSON body (nested dict)
            accept(str): Accept header value; `application/json` is assumed/automatically inserted if omitted
            content_type(str): Content-Type header value; `application/json` is assumed/automatically inserted
                if omitted and `json` is provided.

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
        additional_headers = {}
        if accept is not None:
            additional_headers["Accept"] = accept
        if content_type is not None:
            additional_headers["Content-Type"] = content_type
        async with session.request(
                method=method,
                url=resource,
                params=params,
                data=orjson.dumps(json) if json else None,
                headers=additional_headers,
        ) as r:
            if logger.isEnabledFor(logging.ERROR):
                if params:
                    param_tuples = params.items() if isinstance(params, dict) else params
                logger.debug(
                    "%s %s %s %s %s",
                    method,
                    r.status,
                    resource,
                    "-" if not params else ", ".join(f"{k}={v}" for k, v in param_tuples),
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
            if r.status not in (200, 201, 202, 204):
                raise ValueError(f"Unable to perform {method} request. Status: {r.status}, Response:\n {await r.text()}")
            if r.status in (200, 201) and r.content_length != 0:
                return orjson.loads(await r.read())
            return {}

    async def get(self, resource: str, params: dict | Sequence[tuple[str, str]] | None = None, accept: str | None = "application/json") -> dict:
        return await self.request("GET", resource, params, None, accept=accept)

    async def post(self, resource: str, json: dict | Sequence[tuple[str, str]] | None, accept: str | None = "application/json", content_type: str | None = None) -> dict:
        return await self.request("POST", resource, None, json, accept=accept, content_type=content_type)

    async def put(self, resource: str, json: dict, params: dict | Sequence[tuple[str, str]] | None = None, accept: str | None = "application/json", content_type: str | None = None) -> dict:
        return await self.request("PUT", resource, params, json, accept=accept, content_type=content_type)

    async def post_file(
            self,
            resource: str,
            file: bytes | str | os.PathLike,
            filename: str | None = None,
            form_data: dict[str, str | bytes] | None = None,
            accept: str | None = "application/json",
            content_type: str = "application/octet-stream",
    ) -> dict:
        """Upload a binary file using multipart/form-data.

        Args:
            resource (str):  The resource path.
            file (bytes | str | PathLike):  The file content as bytes or a path to a file on disk.
            filename (str):  The filename for the upload part. Derived from the path if not specified.
            form_data (dict):  Additional file metadata as JSON (nested dict) stored within Cumulocity.
            accept(str): Accept header value; `application/json` is assumed/automatically inserted if omitted
            content_type (str):  The MIME type of the file; `application/octet-stream` is assumed/automatically
                inserted if omitted.

        Returns:
            The JSON response (nested dict), {} if no response body is returned.

        Raises:
            KeyError:  if the resources is not found (404)
            ValueError:  if the request cannot be processes (5xx) or cannot be processed for other reasons
                (only 2xx is accepted).
        """
        if isinstance(file, (str, os.PathLike)):
            path = Path(file)
            file = path.read_bytes()
            filename = filename or path.name
        session = await self.session
        form = aiohttp.FormData()
        form.add_field('file', file, filename=filename, content_type=content_type)
        if form_data:
            for key, value in form_data.items():
                form.add_field(key, value)

        # proper multipart content-type is set by aiohttp
        async with session.request(method="POST", url=resource, data=form, headers={"Accept": accept}) as r:
            if r.status == 401:
                raise UnauthorizedError("POST", resource, message=(await r.json())['message'])
            if r.status == 403:
                raise AccessDeniedError("POST", resource, message=(await r.json())['message'])
            if r.status == 404:
                raise KeyError(f"No such object: {resource}")
            if 500 <= r.status <= 599:
                raise ValueError(f"Invalid POST request. Status: {r.status}, Response:\n {await r.text()}")
            if r.status not in (200, 201, 202, 204):
                raise ValueError(f"Unable to perform POST request. Status: {r.status}, Response:\n {await r.text()}")
            if r.status in (200, 201) and r.content_length != 0:
                return orjson.loads(await r.read())
            return {}

    async def put_file(
            self,
            resource: str,
            file: bytes | str | os.PathLike,
            accept: str | None = "application/json",
            content_type: str = "application/octet-stream",
    ) -> dict:
        """Update a binary file using multipart/form-data.

        Args:
            resource (str): Resource path
            file (str|BinaryIO):  File-like object or a file path
            accept (str|None): Custom Accept header to use (default is
                application/json). Specify '' to send no Accept header.
            content_type (str): Content type of the file sent
                (default is application/octet-stream)

        Returns:
            The JSON response (nested dict), {} if no response body is returned.

        Raises:
            KeyError:  if the resources is not found (404)
            ValueError:  if the request cannot be processes (5xx) or cannot be processed for other reasons
                (only 2xx is accepted).
        """
        if isinstance(file, (str, os.PathLike)):
            path = Path(file)
            file = path.read_bytes()
        session = await self.session
        async with session.request(method="PUT", url=resource, data=file, headers={"Accept": accept}) as r:
            if r.status == 401:
                raise UnauthorizedError("PUT", resource, message=(await r.json())['message'])
            if r.status == 403:
                raise AccessDeniedError("PUT", resource, message=(await r.json())['message'])
            if r.status == 404:
                raise KeyError(f"No such object: {resource}")
            if 500 <= r.status <= 599:
                raise ValueError(f"Invalid PUT request. Status: {r.status}, Response:\n {await r.text()}")
            if r.status not in (200, 201, 202, 204):
                raise ValueError(f"Unable to perform PUT request. Status: {r.status}, Response:\n {await r.text()}")
            if r.status in (200, 201) and r.content_length != 0:
                return orjson.loads(await r.read())
            return {}

    async def get_file(self, resource: str, params: dict | Sequence[tuple[str, str]] | None = None) -> bytes:
        """Download a binary file.

        Args:
            resource (str):  The resource path.
            params (dict|Sequence[tuple]): Additional request parameters

        Returns:
            The file content as bytes.

        Raises:
            KeyError:  if the resource is not found (404)
            ValueError:  if the request cannot be processed (5xx or unexpected status)
        """
        session = await self.session
        async with session.get(url=resource, params=params) as r:
            if r.status == 401:
                raise UnauthorizedError("GET", resource, message=(await r.json())['message'])
            if r.status == 403:
                raise AccessDeniedError("GET", resource, message=(await r.json())['message'])
            if r.status == 404:
                raise KeyError(f"No such object: {resource}")
            if 500 <= r.status <= 599:
                raise ValueError(f"Invalid GET request. Status: {r.status}, Response:\n {await r.text()}")
            if r.status != 200:
                raise ValueError(f"Unable to perform GET request. Status: {r.status}, Response:\n {await r.text()}")
            return await r.read()

    async def delete(self, resource: str, params: dict | Sequence[tuple[str, str]] | None = None) -> dict:
        return await self.request("DELETE", resource, params)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
