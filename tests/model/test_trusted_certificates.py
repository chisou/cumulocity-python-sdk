# Copyright (c) 2026 Christoph Souris

from datetime import datetime as dt, timedelta as td, timezone as tz

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from unittest.mock import AsyncMock, Mock

from pyc8y.model.trusted_certificates import TrustedCertificate, TrustedCertificates

from tests.model.conftest import load_sample_file


@pytest.fixture
def mock_c8y():
    c8y = Mock()
    c8y.tenant_id = "t12345"
    return c8y


def test_parsing():
    """Verify that parsing a TrustedCertificate from JSON works."""
    sample_json = load_sample_file("trusted_certificate.json")[0]
    cert = TrustedCertificate.from_json(sample_json)

    assert cert.fingerprint == sample_json["fingerprint"]
    assert cert.id == cert.fingerprint
    assert cert.name == sample_json["name"]
    assert cert.status == sample_json["status"]
    assert cert.auto_registration_enabled == sample_json["autoRegistrationEnabled"]
    assert cert.is_certificate_authority == sample_json["tenantCertificateAuthority"]
    assert cert.is_ca == cert.is_certificate_authority
    assert cert.certificate_pem == sample_json["certInPemFormat"]
    assert cert.serial == sample_json["serialNumber"]
    assert cert.version == sample_json["version"]
    assert cert.algorithm == sample_json["algorithmName"]
    assert cert.subject == sample_json["subject"]
    assert cert.issuer == sample_json["issuer"]
    assert cert.not_before == sample_json["notBefore"]
    assert cert.not_after == sample_json["notAfter"]


async def test_bulk_create(mock_c8y):
    """Verify that bulk creation works as expected."""
    n_certs = 4
    mock_c8y.post = AsyncMock(return_value={})
    certs = [
        TrustedCertificate(name=str(i))
        for i in range(n_certs)
    ]

    # (1) default mode
    await TrustedCertificates(mock_c8y).create(*certs)
    # -> post called once with all certs
    mock_c8y.post.assert_called_once()
    posted_json = mock_c8y.post.call_args.kwargs["json"]
    assert {str(x) for x in range(n_certs)} == {x["name"] for x in posted_json["certificates"]}

    # (2) explicit batch size
    mock_c8y.post.reset_mock()
    await TrustedCertificates(mock_c8y).create(*certs, batch_size=2)
    assert mock_c8y.post.call_count == 2
    assert {"0", "1"} == {x["name"] for x in mock_c8y.post.call_args_list[0].kwargs["json"]["certificates"]}
    assert {"2", "3"} == {x["name"] for x in mock_c8y.post.call_args_list[1].kwargs["json"]["certificates"]}


@pytest.mark.parametrize(
    "input, expected",
    [
        (["1", "2"], [b"1", b"2"]),
        ([1, 2], [b"1", b"2"]),
        (
            [("1", "2020-01-31T11:22:33Z"), ("2", "2021-01-31T11:22:33Z")],
            [b"1,2020-01-31T11:22:33.000Z", b"2,2021-01-31T11:22:33.000Z"],
        ),
        (
            [("1", dt(2020, 1, 31, 11, 22, 33, tzinfo=tz.utc)), ("2", dt(2021, 1, 31, 11, 22, 33, tzinfo=tz.utc))],
            [b"1,2020-01-31T11:22:33.000Z", b"2,2021-01-31T11:22:33.000Z"],
        ),
        (
            [
                ("1", "2020-01-31T11:22:33Z"),
                "2",
                (3, dt(2021, 1, 31, 11, 22, 33, tzinfo=tz.utc))
            ],
            [b"1,2020-01-31T11:22:33.000Z", b"2", b"3,2021-01-31T11:22:33.000Z"],
        ),
    ],
    ids=[
        "serial-string",
        "serial-number",
        "date-string",
        "date-datetime",
        "mixed",
    ],
)
async def test_revoke_bare_serials(mock_c8y, input, expected):
    """Verify that revoke() writes bare serials as single-column CSV rows."""
    captured = []
    mock_c8y.put_file = AsyncMock()

    await TrustedCertificates(mock_c8y).revoke(*input)
    captured = mock_c8y.put_file.call_args.kwargs["file"].read().splitlines()
    assert captured[1:] == expected


def test_certificate_x509():
    """Verify that certificate_x509 parses the PEM into a real x509.Certificate."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "unit-test-cert")])
    now = dt.now(tz.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - td(minutes=5))
        .not_valid_after(now + td(days=1))
        .sign(private_key, hashes.SHA256())
    )
    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
    cert = TrustedCertificate(certificate_pem=pem)

    parsed = cert.certificate_x509

    assert isinstance(parsed, x509.Certificate)
    assert parsed.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "unit-test-cert"
