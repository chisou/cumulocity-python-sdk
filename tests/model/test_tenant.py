# Copyright (c) 2026 Christoph Souris

import pytest

from pyc8y.model.tenants import Tenant

from tests.model.conftest import load_sample_file


_TENANTS = load_sample_file("tenants.json")


@pytest.mark.parametrize('sample_json', _TENANTS['tenants'])
def test_parsing(sample_json):
    """Verify that parsing a Tenant from JSON works as expected."""
    tenant = Tenant.from_json(sample_json)

    assert tenant.id == sample_json['id']
    assert tenant.parent == sample_json['parent']
    assert tenant.creation_time == sample_json['creationTime']
    assert tenant.status == sample_json['status']
    assert tenant.domain == sample_json['domain']
    assert tenant.admin_name == sample_json['adminName']

    if 'adminEmail' in sample_json:
        assert tenant.admin_email == sample_json['adminEmail']
    if 'company' in sample_json:
        assert tenant.company == sample_json['company']
    if 'contactName' in sample_json:
        assert tenant.contact_name == sample_json['contactName']
    if 'contactPhone' in sample_json:
        assert tenant.contact_phone == sample_json['contactPhone']


def test_parse_applications():
    """Verify that tenant applications are parsed as Application objects."""
    tenant_json = _TENANTS['tenants'][0]
    tenant = Tenant.from_json(tenant_json)

    apps = tenant.applications
    assert len(apps) == 2
    assert apps[0].id == tenant_json['applications']['references'][0]['application']['id']

    owned = tenant.owned_applications
    assert len(owned) == 2
    assert owned[0].id == tenant_json['ownedApplications']['references'][0]['application']['id']


def test_parse_empty_applications():
    """Verify that a tenant with no application references returns empty lists."""
    tenant = Tenant.from_json(_TENANTS['tenants'][1])

    assert not tenant.applications
    assert not tenant.owned_applications


def test_formatting():
    """Verify that to_json formatting works as expected."""
    tenant = Tenant(
        domain='domain.com',
        admin_name='admin_name@email.com',
        admin_email='admin_email@email.com',
        admin_pass='admin_pass',
        company='company name',
        contact_name='contact name',
        contact_phone='contact phone',
    )

    tenant_json = tenant.json

    assert 'id' not in tenant_json
    assert 'parent' not in tenant_json
    assert 'status' not in tenant_json
    assert tenant_json['domain'] == tenant.domain
    assert tenant_json['adminName'] == tenant.admin_name
    assert tenant_json['adminEmail'] == tenant.admin_email
    assert tenant_json['adminPass'] == tenant.admin_pass
    assert tenant_json['company'] == tenant.company
    assert tenant_json['contactName'] == tenant.contact_name
    assert tenant_json['contactPhone'] == tenant.contact_phone
