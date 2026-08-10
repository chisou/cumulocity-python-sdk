# Copyright (c) 2026 Christoph Souris

import base64
import datetime as dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from pyc8y.client import CumulocityClient
from pyc8y.model.trusted_certificates import TrustedCertificate, TrustedCertificateStatus
from pyc8y.rest import AccessDeniedError

from util.testing_util import create_random_name


def generate_certificate(common_name: str) -> tuple[str, ec.EllipticCurvePrivateKey]:
    """Generate a throwaway self-signed certificate."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = dt.datetime.now(dt.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
    return pem, private_key


async def test_round_trip(live_c8y: CumulocityClient):
    """Exercise the full Trusted Certificates lifecycle against a live tenant:

    upload -> generate PoP challenge -> sign & submit PoP -> revoke -> verify revocation -> delete.
    """
    pem, private_key = generate_certificate(create_random_name())
    cert = None
    try:
        # 1) upload (create) the certificate
        cert = await TrustedCertificate(
            live_c8y,
            certificate_pem=pem,
            name=create_random_name(),
            status=TrustedCertificateStatus.ENABLED,
        ).create()
        assert cert.fingerprint
        assert cert.certificate_pem

        # 2) generate a proof-of-possession challenge
        challenged = await live_c8y.trusted_certificates.generate_pop_challenge(cert.fingerprint)
        assert challenged.pop_challenge

        # 3) sign the challenge code with the certificate's private key
        signature = private_key.sign(challenged.pop_challenge.encode(), ec.ECDSA(hashes.SHA256()))
        signed_code = base64.b64encode(signature).decode()

        # 4) submit the signed code to validate proof of possession
        verified = await live_c8y.trusted_certificates.provide_pop_verification(cert.fingerprint, signed_code)
        assert verified.pop_valid is True

        try:
            # 5) revoke the certificate (revoke() wants the serial in hex format)
            serial_hex = f"{int(verified.serial):X}"
            await live_c8y.trusted_certificates.revoke(serial_hex)

            # 6) verify the revocation took effect (CRL is DER-encoded, confirmed live)
            crl_bytes = await live_c8y.trusted_certificates.get_revoked()
            crl = x509.load_der_x509_crl(crl_bytes)
            assert crl.get_revoked_certificate_by_serial_number(int(verified.serial)) is not None
        except AccessDeniedError:
            pytest.skip("Test needs a management tenant and tenant admin role.")

    finally:
        # 7) delete the certificate
        if cert:
            await live_c8y.trusted_certificates.delete(cert)
