# Copyright (c) 2026 Christoph Souris

import csv
import io
from datetime import datetime
from enum import StrEnum
from typing import Sequence, AsyncIterator, Self, TYPE_CHECKING

from pyc8y.model.model_util import coerce_timestring

if TYPE_CHECKING:
    from cryptography import x509

from pyc8y.model.matcher import JsonMatcher
from pyc8y.model.model_base import (
    map_params,
    resolve_page_size,
    CumulocityResource,
    CumulocityObject,
    WithId,
    json_property,
    time_property,
    datetime_property,
    run_batched,
)
from pyc8y.rest import CumulocityRestClient
from pyc8y.types import TrustedCertificatesMeta


class TrustedCertificateStatus(StrEnum):
    """Trusted certificate statuses."""

    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


class TrustedCertificate(WithId, CumulocityObject):
    """Represent a trusted certificate in Cumulocity.

    Instances of this class are returned by functions of the corresponding
    Trusted Certificates API. Use this class to store or retrieve trusted
    certificates.

    See also: https://cumulocity.com/api/core/#tag/Trusted-certificates
    """

    _meta = TrustedCertificatesMeta

    def __init__(
            self,
            c8y: CumulocityRestClient | None = None,
            *,
            certificate_pem: str | None = None,
            name: str | None = None,
            status: str | None = None,
            auto_registration_enabled: bool | None = None,
    ):
        super().__init__(c8y)
        if certificate_pem is not None:
            self._staged_json["certInPemFormat"] = certificate_pem
        self.name = name
        self.status = status
        self.auto_registration_enabled = auto_registration_enabled

    @property
    def id(self):
        return self.fingerprint

    @property
    def resource_path(self) -> str:
        return f"tenant/tenants/{self.c8y.tenant_id}/trusted-certificates"

    name = json_property("name")
    fingerprint = json_property("fingerprint", read_only=True)
    status = json_property("status")
    auto_registration_enabled = json_property[bool]("autoRegistrationEnabled")

    is_certificate_authority = json_property[bool]("tenantCertificateAuthority", read_only=True)
    is_ca = is_certificate_authority
    certificate_pem = json_property("certInPemFormat", read_only=True)
    serial = json_property("serialNumber", read_only=True)
    version = json_property("version", read_only=True)
    algorithm = json_property("algorithmName", read_only=True)
    subject = json_property("subject", read_only=True)
    issuer = json_property("issuer", read_only=True)

    not_before = time_property("notBefore", read_only=True)
    not_before_datetime = datetime_property("notBefore")
    not_after = time_property("notAfter", read_only=True)
    not_after_datetime = datetime_property("notAfter")

    # Note: these are hard deviations from the original naming, focusing on ease of use
    pop_challenge = json_property("proofOfPossessionUnsignedVerificationCode", read_only=True)
    pop_valid = json_property[bool]("proofOfPossessionValid", read_only=True)
    pop_valid_until = time_property("proofOfPossessionVerificationCodeUsableUntil", read_only=True)
    pop_valid_until_datetime = datetime_property("proofOfPossessionVerificationCodeUsableUntil")

    @property
    def certificate_x509(self) -> "x509.Certificate":
        """The certificate, parsed into a `cryptography.x509.Certificate`."""
        try:
            from cryptography import x509
        except ImportError as e:
            raise ImportError("cryptography is required. Install with: pip install pyc8y[cryptography]") from e
        return x509.load_pem_x509_certificate(self.certificate_pem.encode())

    async def create(self, copy: bool = False, *, add_to_truststore: bool | None = None) -> Self:
        """Create this certificate within the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).
            add_to_truststore (bool): If True, the certificate is also added
                to the platform's truststore.

        Returns:
            The created TrustedCertificate. By default, this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._create(copy, add_to_truststore=add_to_truststore)

    async def update(self, copy: bool = False) -> Self:
        """Write changes to the database.

        Note: Only `name`, `status` and `auto_registration_enabled` can be updated.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated TrustedCertificate. By default, this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._update(copy)

    async def apply_to(self, other_fingerprint: str) -> Self:
        """Apply changes made to this certificate to another certificate in the database.

        Note: Only `name`, `status` and `auto_registration_enabled` can be updated.

        Args:
            other_fingerprint (str): Fingerprint of the certificate to update.

        Returns:
            A fresh TrustedCertificate instance representing the updated state.
        """
        return await self._apply_to(other_fingerprint)


class TrustedCertificates(CumulocityResource):
    """Provides access to the Trusted Certificates API.

    This class can be used for get, search for, create, update and
    delete trusted certificates within the Cumulocity database, as well
    as for the proof-of-possession and certificate-revocation flows.

    See also: https://cumulocity.com/api/core/#tag/Trusted-certificates
    """
    _meta = TrustedCertificatesMeta
    _object_type = TrustedCertificate

    def __init__(self, c8y: CumulocityRestClient):
        super().__init__(c8y)

    @property
    def resource_path(self) -> str:
        return f"tenant/tenants/{self.c8y.tenant_id}/trusted-certificates"

    def build_object_path(self, object_id: str) -> str:
        return f"{self.resource_path}/{object_id}"

    async def get(self, fingerprint: str) -> TrustedCertificate:
        """Retrieve a specific trusted certificate from the database.

        Args:
            fingerprint (str): The fingerprint (database ID) of the certificate

        Returns:
            A TrustedCertificate instance representing the object in the database.
        """
        return await self._get(fingerprint)

    async def get_certificate_authority(self) -> TrustedCertificate:
        """Retrieve the tenant's certificate authority.

        Returns:
            The TrustedCertificate instance marked as this tenant's certificate authority.

        Raises:
            KeyError: if no certificate authority is defined for this tenant.
        """
        certs = await self.get_all(certificate_authority=True, limit=1)
        if not certs:
            raise KeyError("No certificate authority defined.")
        return certs[0]

    def select(
            self,
            expression: str | None = None,
            *,
            certificate_authority: bool | None = None,
            limit: int | None = 5,
            include: str | JsonMatcher | None = None,
            exclude: str | JsonMatcher | None = None,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
            **kwargs,
    ) -> AsyncIterator[TrustedCertificate]:
        """Query the database for trusted certificates and iterate over the results.

        This function is implemented in a lazy fashion - results will only be
        fetched from the database as long there is a consumer for them.

        All parameters are considered to be filters, limiting the result set
        to objects which meet the filters specification. Filters can be
        combined (as defined in the Cumulocity REST API).

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided
            certificate_authority (bool): Only include the tenant's certificate
                authority (or exclude it, if False)
            limit (int | None): Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            include (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The inclusion is applied first.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            exclude (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The exclusion is applied second.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            page_size (int | None): Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int): Pull a specific page; this effectively disables
                automatic follow-up page retrieval.
            as_values: (str|tuple|list[str|tuple]): Don't parse objects, but
                directly extract the values at certain JSON paths as tuples;
                If the path is not defined in a result, None is used; Specify
                a tuple to define a proper default value for each path.
            workers (int): The number of parallel processes to use

        Returns:
            AsyncIterator of TrustedCertificate instances

        See also:
            https://github.com/bytebutcher/pydfql/blob/main/docs/USER_GUIDE.md#4-query-language
        """
        page_size = resolve_page_size(page_size, limit, include, exclude)
        params = (
            map_params(
                certificate_authority = certificate_authority,
                page_size=page_size,
                **kwargs,
            )
            if not expression
            else ()
        )
        return self._iterate(
            expression=expression,
            params=params,
            page_number=page_number,
            limit=limit,
            include=include,
            exclude=exclude,
            as_values=as_values,
            workers=workers,
            preserve_order=False,
        )

    async def get_all(
            self,
            expression: str | None = None,
            *,
            certificate_authority: bool | None = None,
            limit: int | None = 5,
            include: str | JsonMatcher | None = None,
            exclude: str | JsonMatcher | None = None,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
            **kwargs,
    ) -> list[TrustedCertificate]:
        """Query the database for trusted certificates and return the results as a list.

        This function is a greedy version of the `select` function. All
        available results are read immediately and returned as a list.

        See `select` for a documentation of arguments.

        Returns:
            List of TrustedCertificate instances
        """
        return [
            x
            async for x in self.select(
                expression=expression,
                certificate_authority=certificate_authority,
                limit=limit,
                include=include,
                exclude=exclude,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
                **kwargs
            )
        ]

    async def create(
            self,
            *certificates: TrustedCertificate,
            batch_size: int | None = None,
            workers: int | None = None) -> None:
        """Create trusted certificates within the database.

        Uses the bulk import endpoint (`{resource_path}/bulk`), sending as
        few requests as possible instead of one request per certificate.

        Args:
            *certificates (TrustedCertificate): Collection of TrustedCertificate instances
            batch_size (int): Maximum number of certificates per request; if
                None (default), all certificates are sent in a single request.
                Set this if the tenant/API enforces a limit on payload size.
            workers (int): Number of parallel requests; only relevant when
                `batch_size` splits the certificates into multiple chunks.
        """
        await self._create_bulk(
            *certificates, path=f"{self.resource_path}/bulk", batch_size=batch_size, workers=workers
        )

    async def update(self, *certificates: TrustedCertificate, workers: int | None = None) -> None:
        """Update trusted certificates within the database.

        Note: Only `name`, `status` and `auto_registration_enabled` can be updated.

        Args:
            *certificates (TrustedCertificate): Collection of TrustedCertificate instances
            workers (int): Number of parallel requests
        """
        await self._update(*certificates, workers=workers)

    async def delete(self, *certificates: str | TrustedCertificate, workers: int | None = None) -> None:
        """Delete trusted certificates from the database.

        Args:
            *certificates (str|TrustedCertificate): Certificate objects or fingerprints to delete
            workers (int): Number of parallel requests
        """
        await self._delete(*certificates, workers=workers)

    async def apply_to(
            self,
            certificate: TrustedCertificate | dict,
            *fingerprints: str,
            workers: int | None = None,
    ) -> None:
        """Apply changes made to a single instance to other certificates in the database.

        Note: Only `name`, `status` and `auto_registration_enabled` can be updated.

        Args:
            certificate (TrustedCertificate|dict): Object serving as model for the update or
                simply a dictionary representing the diff JSON.
            *fingerprints (str): A collection of fingerprints of certificates to update
            workers (int): The number of parallel processes to use
        """
        await self._apply_to(certificate, *fingerprints, workers=workers)


    async def generate_pop_challenge(
            self,
            fingerprint: str,
    ) -> TrustedCertificate:
        """Generate a new proof-of-possession verification code for a certificate.

        Args:
            fingerprint (str): Fingerprint of the certificate to challenge.

        Returns:
            A fresh TrustedCertificate instance carrying the new unsigned
            verification code (`proof_of_possession_code`).
        """
        return self._object_type.from_json(
            await self.c8y.post(
                f"tenant/tenants/{self.c8y.tenant_id}/trusted-certificates-pop/{fingerprint}/verification-code",
                json=None,
            ),
            c8y=self.c8y,  # inject c8y instance
        )

    async def provide_pop_verification(
            self,
            fingerprint: str,
            verification_code: str,
    ) -> TrustedCertificate:
        """Submit a signed proof-of-possession verification code for a certificate.

        Args:
            fingerprint (str): Fingerprint of the certificate being verified.
            verification_code (str): The unsigned verification code (obtained
                via `generate_pop_challenge`), signed with the certificate's
                private key.

        Returns:
            A fresh TrustedCertificate instance reflecting the verification result.
        """
        return self._object_type.from_json(
            await self.c8y.post(
                f"tenant/tenants/{self.c8y.tenant_id}/trusted-certificates-pop/{fingerprint}/pop",
                json={"proofOfPossessionSignedVerificationCode": verification_code},
            ),
            c8y=self.c8y,  # inject c8y instance
        )

    async def confirm_pop(
            self,
            tenant_id: str,
            fingerprint: str,
    ) -> TrustedCertificate:
        """Confirm that a tenant has proved possession of a certificate.

        Note: This can only be invoked from the management tenant, and
        targets a certificate belonging to `tenant_id` (not necessarily the
        caller's own tenant).

        Args:
            tenant_id (str): ID of the tenant owning the certificate.
            fingerprint (str): Fingerprint of the certificate to confirm.

        Returns:
            A fresh TrustedCertificate instance reflecting the confirmed state.
        """
        return self._object_type.from_json(
            await self.c8y.post(
                f"tenant/tenants/{tenant_id}/trusted-certificates-pop/{fingerprint}/confirmed",
                json=None,
            ),
            c8y=self.c8y,  # inject c8y instance
        )

    async def revoke(
            self,
            *crls: tuple[str, datetime|str] | str,
            batch_size: int | None = None,
            workers: int | None = None,
    ) -> None:
        """Revoke a set of certificates.

        Note: This can only be invoked from the management tenant.

        Args:
            *crls (tuple[str, datetime|str] | str): Certificates to revoke,
                each specified either as a bare serial number, or as a
                (serial, revocation date) tuple. The serial must be in
                hexadecimal format.
            batch_size (int): Maximum number of entries per request; if
                None (default), all entries are sent in a single request.
            workers (int): Number of parallel requests; only relevant when
                `batch_size` splits the entries into multiple chunks.
        """
        batches = (
            [crls] if not batch_size
            else [crls[i : i + batch_size] for i in range(0, len(crls), batch_size)]
        )

        async def post_batch(batch: Sequence) -> None:
            # newline="" disables StringIO's own newline handling, leaving csv.writer's
            # \r\n row terminators untouched (see the csv module docs' own warning about this)
            with io.StringIO(newline="") as text_buffer:
                csv_writer = csv.writer(text_buffer)
                csv_writer.writerow(["SERIAL NO.", "REVOCATION DATE"])
                for item in batch:
                    if isinstance(item, tuple):
                        csv_writer.writerow([item[0], coerce_timestring(item[1])])
                    else:
                        csv_writer.writerow([item])
                csv_bytes = text_buffer.getvalue().encode("utf-8")

            await self.c8y.put_file(
                "tenant/trusted-certificates/settings/crl",
                file=io.BytesIO(csv_bytes),
                content_type="text/csv",
                multipart=True,
            )

        await run_batched(batches, workers, post_batch)

    async def get_revoked(self) -> bytes:
        """Download the currently revoked certificates.

        Returns:
            The currently revoked certificates in PKIX/CRL format as binary file bytes.
        """
        file, _ = await self.c8y.get_file("tenant/trusted-certificates/settings/crl")
        return file


