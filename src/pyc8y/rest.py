# Copyright (c) 2026 Christoph Souris

import logging
import os
import ssl
from asyncio import Semaphore
from collections import Counter
from contextlib import asynccontextmanager, nullcontext
from enum import StrEnum
from pathlib import Path
from typing import Awaitable, BinaryIO, Callable, NamedTuple, Self, Sequence, Any, Mapping

import aiohttp
import certifi
import orjson

from pyc8y.auth import Auth, BasicAuth, BearerAuth


class FileDownload(NamedTuple):
    """Result of a binary file download."""
    content: bytes
    filename: str | None

logger = logging.getLogger(__name__)


def loggable_params(params):
    """Provide a log-friendly formatted string of HTTP parameters."""
    if not params:
        return "-"
    return ", ".join(f"{k}={v}" for k, v in params.items())


class ProcessingMode(StrEnum):
    """Cumulocity REST API processing modes."""

    PERSISTENT = "PERSISTENT"
    TRANSIENT = "TRANSIENT"
    QUIESCENT = "QUIESCENT"


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
        super().__init__(f"HTTP {code}: {method} {url} - {message}")
        self.method = method
        self.url = url
        self.code = code
        self.message = message


class UnauthorizedError(HttpError):
    """Error raised for unauthorized access."""

    def __init__(self, method: str, url: str, message: str = "Unauthorized."):
        super().__init__(method, url, 401, message)


class MissingTfaError(UnauthorizedError):
    """Error raised for unauthorized access."""

    def __init__(self, method: str, url: str, message: str = "Missing TFA Token."):
        super().__init__(method, url, message)


class AccessDeniedError(HttpError):
    """Error raised for denied access."""

    def __init__(self, method: str, url: str, message: str = "Access denied."):
        super().__init__(method, url, 403, message)


class BatchError(Exception):
    """Error raised after a batch processing."""

    def __init__(self, errors: list[BaseException]):
        super().__init__(self._build_message(errors))
        self.errors = errors

    @staticmethod
    def _build_message(errors) -> str:
        counts = Counter(type(e).__name__ for e in errors)
        parts = [f"{name}({count})" if count > 1 else name for name, count in counts.items()]
        return f"Batch processing raised {len(errors)} errors: {', '.join(parts)}"


class CumulocityRestClient(object):

    def __init__(
        self,
        base_url: str,
        tenant_id: str,
        auth: Auth,
        application_key: str | None = None,
        processing_mode: str | None = None,
        connector_factory: "Callable[[], Awaitable[aiohttp.BaseConnector]] | None" = None,
        semaphore: Semaphore | None = None,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.tenant_id = tenant_id
        self.auth = auth
        self.application_key = application_key
        self.processing_mode = processing_mode
        self._connector_factory = connector_factory
        self._session = None
        self._semaphore = semaphore if semaphore is not None else nullcontext()

    async def __aenter__(self) -> Self:
        _ = await self.session  # ensure session is created
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    @property
    async def session(self) -> aiohttp.ClientSession:
        if not self._session:
            headers = {
                "Authorization": self.auth.build_auth_header(),
            }
            if self.application_key:
                headers["X-Cumulocity-Application-Key"] = self.application_key
            if self.processing_mode:
                headers["X-Cumulocity-Processing-Mode"] = self.processing_mode
            if self._connector_factory is not None:
                connector = await self._connector_factory()
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    connector_owner=False,
                    base_url=self.base_url,
                    headers=headers,
                    skip_auto_headers=frozenset({"Accept"}),
                )
            else:
                ssl_context = ssl.create_default_context(cafile=certifi.where())
                self._session = aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(ssl=ssl_context),
                    base_url=self.base_url,
                    headers=headers,
                    skip_auto_headers=frozenset({"Accept"}),
                )
        return self._session

    @property
    def username(self):
        return self.auth.get_username()

    @classmethod
    async def authenticate(
        cls,
        base_url: str,
        tenant_id: str,
        username: str,
        password: str,
        tfa_token: str | None = None,
    ) -> tuple[Auth, str | None]:
        """Authenticate a user using OAI Secure login method.

        Args:
            base_url (str):  Cumulocity base URL, e.g. https://cumulocity.com
            tenant_id (str):  The ID of the tenant to connect to
            username (str):  Username
            password (str):  User password
            tfa_token (str):  Currently valid two-factor authorization token

        Returns:
            A ready to use Auth instance and optionally an XSRF token.
        """

        def build_url(resource):
            return f"{base_url.rstrip('/')}/{resource.lstrip('/')}"

        async with aiohttp.ClientSession() as session:
            ssl_context = ssl.create_default_context(cafile=certifi.where())

            # read login options
            login_options = []
            async with session.get(build_url("tenant/loginOptions"), ssl=ssl_context) as response:
                if response.status == 200:
                    login_options = [x["type"] for x in (await response.json())["loginOptions"]]
                else:
                    login_options = ["BASIC", "OAUTH2_INTERNAL"]
                    logger.error("Unable to determine login options. Using default.")
            logger.info(f"Available login options: {', '.join(login_options)}")

            # try OAuth internal (with/without 2nd factor)
            if "OAUTH2_INTERNAL" in login_options:
                if not username or not password:
                    logger.info("OAuth Internal authentication needs username/password. Skipping.")
                else:
                    logger.info("Attempting login using OAUTH2_INTERNAL ...")
                    # include 2nd factor token if available
                    form_data = {"grant_type": "PASSWORD", "username": username, "password": password}
                    if tfa_token:
                        form_data["tfa_token"] = tfa_token
                    async with session.post(
                        build_url(f"tenant/oauth?tenant_id={tenant_id}"), data=form_data, ssl=ssl_context
                    ) as response:
                        if response.status == 200:
                            logger.info("Login successful.")
                            auth_cookie = response.cookies["authorization"]
                            xsrf_cookie = response.cookies.get("XSRF-TOKEN")
                            return BearerAuth(token=auth_cookie.value), xsrf_cookie.value if xsrf_cookie else None
                        # login failed, checking known reasons
                        response_json = orjson.loads(await response.text() or "") or {}
                        if response.status == 401:
                            message:str|None = response_json.get("message", None)
                            # 1st request might fail due to missing TFA code
                            if message and any(x in message for x in ["TOTP", "TFA"]):
                                raise MissingTfaError(HttpMethod.POST, str(response.url), message)
                            raise UnauthorizedError(HttpMethod.POST, str(response.url), str(message))
                        # this should never happen
                        message = response_json.get("message", "Invalid request!")
                        raise HttpError(HttpMethod.POST, str(response.url), response.status, message)

            # try basic authentication
            if "BASIC" in login_options:
                if not username or not password:
                    logger.info("Basic authentication needs username/password. Skipping.")
                else:
                    logger.info("Attempting login using Basic Authentication ...")
                    auth = BasicAuth(username, password)
                    async with session.get(
                        build_url("tenant/currentTenant"),
                        headers={"Authorization": auth.build_auth_header()},
                        ssl=ssl_context,
                    ) as response:
                        if response.status == 200:
                            return auth, None
                        response_json = orjson.loads(await response.text() or "") or {}
                        if response.status == 401:
                            raise UnauthorizedError(HttpMethod.GET, str(response.url), response_json.get("message", "No detailed error provided."))
                        # this should never happen
                        message = response_json.get("message", "Invalid request!")
                        raise HttpError(HttpMethod.GET, str(response.url), response.status, message)

            raise ValueError(
                f"Unable to authenticate with Cumulocity. Unsupported login options: {' ,'.join(login_options)}."
            )

    async def request(
        self,
        method: str,
        resource: str,
        params: Sequence[tuple[str, Any]] | Mapping[str, Any] = (),
        json: dict | None = None,
        accept: str | None = None,
        content_type: str | None = None,
    ) -> dict:
        """Perform an HTTP request.

        Args:
            method(str): The HTTP method to use.
            resource(str): The resource path.
            params (Sequence | Mapping): Additional request parameters
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
        async with self._semaphore:
            async with session.request(
                method=method,
                url=resource,
                params=params,
                data=orjson.dumps(json) if json is not None else None,
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
                    raise UnauthorizedError(method, resource, message=(await r.json())["message"])
                if r.status == 403:
                    raise AccessDeniedError(method, resource, message=(await r.json())["message"])
                if r.status == 404:
                    raise KeyError(f"No such object: {resource}")
                if 500 <= r.status <= 599:
                    raise ValueError(f"Invalid {method} request. Status: {r.status}, Response:\n {await r.text()}")
                if r.status not in (200, 201, 202, 204):
                    raise ValueError(
                        f"Unable to perform {method} request. Status: {r.status}, Response:\n {await r.text()}"
                    )
                if r.status in (200, 201) and r.content_length != 0:
                    return orjson.loads(await r.read())
                return {}

    async def get(
        self,
        resource: str,
        *,
        params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
        accept: str | None = "application/json",
    ) -> dict:
        return await self.request("GET", resource, params or (), None, accept=accept)

    async def post(
        self,
        resource: str,
        *,
        params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
        json: dict | None = None,
        accept: str | None = "application/json",
        content_type: str | None = None,
    ) -> dict:
        return await self.request("POST", resource, params or (), json or {}, accept=accept, content_type=content_type)

    async def put(
        self,
        resource: str,
        *,
        params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
        json: dict | None = None,
        accept: str | None = "application/json",
        content_type: str | None = None,
    ) -> dict:
        return await self.request("PUT", resource, params or (), json or {}, accept=accept, content_type=content_type)

    async def post_file(
        self,
        resource: str,
        file: str | os.PathLike | BinaryIO,
        filename: str | None = None,
        form_data: dict[str, str | bytes] | None = None,
        accept: str | None = None,
        content_type: str | None = None,
    ) -> dict:
        """Upload a binary file using multipart/form-data.

        Args:
            resource (str):  The resource path.
            file (str | PathLike | BinaryIO):  File path or file-like object to upload.
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
        accept = accept or "application/json"
        content_type = content_type or "application/octet-stream"
        session = await self.session

        async def post(file_obj):
            form = aiohttp.FormData()
            form.add_field("file", file_obj, filename=filename, content_type=content_type)
            if form_data:
                for key, value in form_data.items():
                    form.add_field(key, value)
            # proper multipart content-type is set by aiohttp
            async with session.request(method="POST", url=resource, data=form, headers={"Accept": accept}) as r:
                if r.status == 401:
                    raise UnauthorizedError("POST", resource, message=(await r.json())["message"])
                if r.status == 403:
                    raise AccessDeniedError("POST", resource, message=(await r.json())["message"])
                if r.status == 404:
                    raise KeyError(f"No such object: {resource}")
                if 500 <= r.status <= 599:
                    raise ValueError(f"Invalid POST request. Status: {r.status}, Response:\n {await r.text()}")
                if r.status not in (200, 201, 202, 204):
                    raise ValueError(
                        f"Unable to perform POST request. Status: {r.status}, Response:\n {await r.text()}"
                    )
                if r.status in (200, 201) and r.content_length != 0:
                    return orjson.loads(await r.read())
                return {}

        if isinstance(file, (str, os.PathLike)):
            path = Path(file)
            filename = filename or path.name
            with open(path, "rb") as f:
                return await post(f)
        else:
            filename = filename or getattr(file, "name", None)
            return await post(file)

    async def put_file(
        self,
        resource: str,
        file: str | os.PathLike | BinaryIO,
        accept: str | None = None,
        content_type: str | None = None,
    ) -> dict:
        """Update a binary file using multipart/form-data.

        Args:
            resource (str): Resource path
            file (str | PathLike | BinaryIO):  File path or file-like object to upload.
            accept (str|None): Custom Accept header to use (default is
                application/json).
            content_type (str): Content type of the file sent
                (default is application/octet-stream)

        Returns:
            The JSON response (nested dict), {} if no response body is returned.

        Raises:
            KeyError:  if the resources is not found (404)
            ValueError:  if the request cannot be processes (5xx) or cannot be processed for other reasons
                (only 2xx is accepted).
        """
        accept = accept or "application/json"
        content_type = content_type or "application/octet-stream"
        session = await self.session

        async def put(file_obj):
            async with session.request(
                method="PUT", url=resource, data=file_obj, headers={"Accept": accept, "Content-Type": content_type}
            ) as r:
                if r.status == 401:
                    raise UnauthorizedError("PUT", resource, message=(await r.json())["message"])
                if r.status == 403:
                    raise AccessDeniedError("PUT", resource, message=(await r.json())["message"])
                if r.status == 404:
                    raise KeyError(f"No such object: {resource}")
                if 500 <= r.status <= 599:
                    raise ValueError(f"Invalid PUT request. Status: {r.status}, Response:\n {await r.text()}")
                if r.status not in (200, 201, 202, 204):
                    raise ValueError(f"Unable to perform PUT request. Status: {r.status}, Response:\n {await r.text()}")
                if r.status in (200, 201) and r.content_length != 0:
                    return orjson.loads(await r.read())
                return {}

        if isinstance(file, (str, os.PathLike)):
            with open(file, "rb") as f:
                return await put(f)
        else:
            return await put(file)

    async def get_file(self, resource: str, params: dict | Sequence[tuple[str, str]] | None = None) -> FileDownload:
        """Download a binary file.

        Args:
            resource (str):  The resource path.
            params (dict|Sequence[tuple]): Additional request parameters

        Returns:
            A FileDownload tuple of file content bytes and filename (from Content-Disposition, if present).

        Raises:
            KeyError:  if the resource is not found (404)
            ValueError:  if the request cannot be processed (5xx or unexpected status)
        """
        session = await self.session
        async with session.get(url=resource, params=params) as r:
            if r.status == 401:
                raise UnauthorizedError("GET", resource, message=(await r.json())["message"])
            if r.status == 403:
                raise AccessDeniedError("GET", resource, message=(await r.json())["message"])
            if r.status == 404:
                raise KeyError(f"No such object: {resource}")
            if 500 <= r.status <= 599:
                raise ValueError(f"Invalid GET request. Status: {r.status}, Response:\n {await r.text()}")
            if r.status != 200:
                raise ValueError(f"Unable to perform GET request. Status: {r.status}, Response:\n {await r.text()}")
            cd = r.content_disposition
            filename = cd.filename if cd is not None else None
            return FileDownload(content=await r.read(), filename=filename)

    @asynccontextmanager
    async def stream_file(self, resource: str, params: dict | Sequence[tuple[str, str]] | None = None):
        """Stream a binary file without loading it fully into memory.

        Args:
            resource (str):  The resource path.
            params (dict|Sequence[tuple]): Additional request parameters

        Yields:
            aiohttp.StreamReader: The response content stream.

        Raises:
            KeyError:  if the resource is not found (404)
            ValueError:  if the request cannot be processed (5xx or unexpected status)

        Example::

            async with client.stream_file("/inventory/binaries/123") as content:
                async with aiofiles.open("file.bin", "wb") as f:
                    async for chunk in content.iter_chunked(65536):
                        await f.write(chunk)
        """
        session = await self.session
        async with session.get(url=resource, params=params) as r:
            if r.status == 401:
                raise UnauthorizedError("GET", resource, message=(await r.json())["message"])
            if r.status == 403:
                raise AccessDeniedError("GET", resource, message=(await r.json())["message"])
            if r.status == 404:
                raise KeyError(f"No such object: {resource}")
            if 500 <= r.status <= 599:
                raise ValueError(f"Invalid GET request. Status: {r.status}, Response:\n {await r.text()}")
            if r.status != 200:
                raise ValueError(f"Unable to perform GET request. Status: {r.status}, Response:\n {await r.text()}")
            yield r.content

    async def delete(self, resource: str, params: Mapping[str, Any] | Sequence[tuple[str, Any]] = ()) -> dict:
        return await self.request("DELETE", resource, params)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
