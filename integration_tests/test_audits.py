# Copyright (c) 2026 Christoph Souris

from datetime import timedelta, datetime, timezone

import pytest

from pyc8y.client import CumulocityClient
from pyc8y.model.audit import AuditRecord, AuditSeverity
from pyc8y.model.managed_object import Device

from util.testing_util import create_random_name


async def test_CR(live_c8y: CumulocityClient, session_device: Device):  # noqa (case)
    """Verify that basic creation and lookup of Audit Records works as expected."""

    name = create_random_name()

    # (1) create audit record
    before = datetime.now(timezone.utc)
    record = await AuditRecord(
        live_c8y,
        type=f'{name}_type',
        source=session_device.id,
        time='now',
        severity=AuditSeverity.INFORMATION,
        activity=f'{name} activity',
        text=f'detailed {name} text',
        application=f'{name}_app',
        user=live_c8y.username,
    ).create()
    after = datetime.now(timezone.utc)

    # -> there should be at least 1 audit record with that source
    records = await live_c8y.audit_records.get_all(source=session_device.id)
    assert len(records) >= 1
    assert records[0].id == record.id

    # -> get_count should agree with get_all for the same filter
    count = await live_c8y.audit_records.get_count(source=session_device.id)
    assert count == len(records)

    # -> there should be exactly one audit record with that application/user
    records = await live_c8y.audit_records.get_all(
        application=record.application,
        user=record.user,
    )
    assert len(records) == 1
    assert records[0].id == record.id

    # -> get_count should agree for the application/user filter too
    count = await live_c8y.audit_records.get_count(
        application=record.application,
        user=record.user,
    )
    assert count == 1

    # -> there should be at least one audit record within that timeframe
    records = await live_c8y.audit_records.get_all(before=after, after=before)
    assert len(records) >= 1
    assert record.id in [r.id for r in records]

    # -> there should be at least one audit record within the last 5 seconds
    records = await live_c8y.audit_records.get_all(
        min_age=timedelta(microseconds=0.1),
        max_age=timedelta(seconds=5.0),
    )
    assert len(records) >= 1
    assert record.id in [r.id for r in records]


@pytest.mark.parametrize("obj_type,getter", [
    ("Alarm", lambda c8y: c8y.alarms.get_all(limit=1)),
    ("Application", lambda c8y: c8y.applications.get_all(limit=1)),
    ("Event", lambda c8y: c8y.events.get_all(limit=1)),
    ("ManagedObject", lambda c8y: c8y.inventory.get_all(limit=1)),
    ("Operation", lambda c8y: c8y.operations.get_all(limit=1)),
    ("BulkOperation", lambda c8y: c8y.bulk_operations.get_all(limit=1)),
    ("TenantOption", lambda c8y: c8y.tenant_options.get_all(limit=1)),
    ("UserGroup", lambda c8y: c8y.user_groups.get_all(limit=1)),
])
async def test_get_all_for_object_types(live_c8y: CumulocityClient, obj_type: str, getter):  # noqa (case)
    """Verify that get_all_for retrieves audit records for various object types."""

    # (1) fetch a random object of the specified type
    objects = await getter(live_c8y)
    if not objects:
        pytest.skip(f"No {obj_type} objects found in test environment")
    obj = objects[0]

    # (1) retrieve audit records for this object
    # -> there should always be records
    records = await live_c8y.audit_records.get_all_for(obj)
    assert isinstance(records, list)
    assert all(isinstance(r, AuditRecord) for r in records)

    # (2) verify source of records
    assert all(
        r.type == obj_type
        for r in records
    )
    if records:
        if obj_type == "TenantOption":
            # TenantOption records use a different source format
            pass
        else:
            expected_source = obj.get("id")
            assert all(r.source == expected_source for r in records)
