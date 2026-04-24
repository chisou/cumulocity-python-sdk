# Copyright (c) 2026 Christoph Souris

import base64
import json
from dataclasses import dataclass
import time
from typing import Self, Protocol


class JWT:
    """Simple JWT toolkit.

    This class is used to parse Cumulocity's JWT tokens.
    """

    def __init__(self, token: str | bytes):
        self.token = token if isinstance(token, bytes) else token.encode("utf-8")
        self._body: dict | None = None

    @property
    def payload(self):
        """Return the JWT payload as JSON document."""
        if not self._body:
            jwt_parts = self.token.split(b".")
            if len(jwt_parts) != 3:
                raise ValueError("Unexpected token format (Invalid number of parts, not an JWT?).")
            # The JWT body might not be padded, hence we add padding
            # characters which are ignored if they are not necessary.
            # See: https://gist.github.com/perrygeo/ee7c65bb1541ff6ac770,
            # https://stackoverflow.com/questions/2941995
            body = jwt_parts[1] + b"=="
            self._body = json.loads(base64.b64decode(body))
        return self._body

    @property
    def username(self):
        """Read the username from the token payload."""
        return self.get_claim("sub")

    @property
    def tenant_id(self):
        """Read the tenant ID from the token payload."""
        return self.get_claim("ten")

    def get_claim(self, claim: str):
        """Read a claim from the token payload."""
        return self.payload[claim]

    def get_valid_seconds(self):
        """Return the number of seconds the token before the tokens expires.

        Returns:
            The number of seconds the token remains valid.
        """
        return self.payload["exp"] - time.time()

    def is_valid(self, min_seconds: int = None):
        """Check whether the token is valid.

        Args:
            min_seconds: Minimum number of seconds of validity.
        """
        if not min_seconds:
            min_seconds = 0
        return time.time() + min_seconds > int(self.payload["exp"])


class Auth(Protocol):
    """Protocol class for auth providers."""

    def get_username(self) -> str:
        """Read username from auth info."""
        ...

    def get_tenant_id(self) -> str:
        """Read tenant ID from auth info."""
        ...

    def build_auth_header(self) -> str:
        """Build an HTTP auth header."""  # TODO: check if this documentation is visible in docs and code hints
        ...


@dataclass(frozen=True, slots=True)
class BasicAuth(Auth):
    """Basic auth provider."""

    username: str
    password: str

    @classmethod
    def parse(cls, auth_value: str) -> Self:
        decoded = base64.b64decode(bytes(auth_value, "utf-8"))
        parts = [x.decode("utf-8") for x in decoded.split(b":", 1)]
        return cls(username=parts[0], password=parts[1])

    def get_username(self) -> str:
        return self.username.split("/", 1)[-1]

    def get_tenant_id(self) -> str:
        i = self.username.index("/")
        if i == -1:
            raise ValueError(f"Unable to isolate tenant ID from username: {self.username}")
        return self.username[:i]

    def build_auth_header(self) -> str:
        token = f"{self.username}:{self.password}"
        return f"Basic {base64.b64encode(token.encode()).decode()}"


@dataclass(frozen=True, slots=True)
class BearerAuth(Auth):
    """Bearer auth provider."""

    token: str

    @classmethod
    def parse(cls, auth_value: str) -> Self:
        return cls(auth_value)

    def get_username(self) -> str:
        return self.token  # TODO: read from JWT token

    def get_tenant_id(self) -> str:
        try:
            return JWT(self.token).tenant_id
        except KeyError:
            raise ValueError("Unable to resolve tenant ID. JWT does not appear to include it.")

    def build_auth_header(self) -> str:
        return f"Bearer {self.token}"


def parse_auth(auth_string: str) -> Auth:
    """Parse a given auth string into a corresponding auth object.

    Args:
        auth_string (str):  Complete Auth string (including the type prefix
            like BASIC etc.) as it comes with an Authorization HTTP header

    Returns:
        An Auth-like instance for this auth string.
    """
    auth_type, auth_value = auth_string.split(" ")

    if auth_type.upper() == "BASIC":
        return BasicAuth.parse(auth_value)

    if auth_type.upper() == "BEARER":
        return BearerAuth.parse(auth_value)

    raise ValueError(f"Unexpected authorization header type: {auth_type}")
