# Copyright (c) 2026 Christoph Souris

import pytest

from pyc8y.model.audit import AuditRecord, Type, Severity, Change

from tests.model.conftest import load_sample_file




@pytest.mark.parametrize('sample_json', load_sample_file("audit_records.json")['auditRecords'])
def test_parsing(sample_json):
    """Verify that parsing an AuditRecord from JSON works."""
    record = AuditRecord.from_json(sample_json)

    assert record.id == sample_json['id']
    assert record.type == sample_json['type']
    assert record.activity == sample_json['activity']
    assert record.text == sample_json['text']
    assert record.time == sample_json['time']
    assert record.creation_time == sample_json['creationTime']
    assert record.user == sample_json['user']

    if 'source' in sample_json:
        assert record.source == sample_json['source']['id']
    if 'severity' in sample_json:
        assert record.severity == sample_json['severity']
    if 'application' in sample_json:
        assert record.application == sample_json['application']
    if 'changes' in sample_json:
        changes = record.changes
        assert isinstance(changes, tuple)
        assert len(changes) == len(sample_json['changes'])
        for i, c in enumerate(changes):
            assert c.attribute == sample_json['changes'][i]['attribute']
            assert c.type == sample_json['changes'][i]['type']
            assert c.new_value == sample_json['changes'][i]['newValue']
            assert c.previous_value == sample_json['changes'][i]['previousValue']
    else:
        assert record.changes is None


def test_formatting():
    """Verify that to_json formatting works for a full AuditRecord."""
    record = AuditRecord(
        type=Type.ALARM,
        time='2023-03-23T22:33:44.555Z',
        source='source-id',
        activity='audit activity',
        text='audit text',
        severity=Severity.INFORMATION,
        application='some application',
        user='some@cumulocity.com',
        changes=[
            Change(attribute='attr', new_value='new', previous_value='old', type='type'),
            Change(attribute='attr2', new_value='new2', previous_value='old2', type='type2'),
        ],
        customFragment={'value': 12},
    )

    record_json = record.to_json()

    assert record_json['type'] == Type.ALARM
    assert record_json['source'] == {'id': 'source-id'}
    assert record_json['severity'] == Severity.INFORMATION
    assert record_json['activity'] == 'audit activity'
    assert record_json['text'] == 'audit text'
    assert record_json['application'] == 'some application'
    assert record_json['user'] == 'some@cumulocity.com'
    assert record_json['time'] == '2023-03-23T22:33:44.555Z'
    assert 'creationTime' not in record_json

    assert len(record_json['changes']) == 2
    assert record_json['changes'][1]['attribute'] == 'attr2'
    assert record_json['changes'][1]['newValue'] == 'new2'
    assert record_json['changes'][1]['previousValue'] == 'old2'

    assert record_json['customFragment'] == {'value': 12}


def test_no_changes():
    """Verify that the changes fragment is absent when not provided."""
    record = AuditRecord(type='SomeType')
    assert 'changes' not in record.to_json()
    assert record.changes is None


def test_empty_changes():
    """Verify that the changes fragment can be present but empty."""
    record = AuditRecord(type='SomeType', changes=[])
    assert 'changes' in record.to_json()
    assert len(record.to_json()['changes']) == 0


def test_changes_are_immutable():
    """Verify that the changes property returns an immutable sequence."""
    fixture = load_sample_file("audit_records.json")
    record = AuditRecord.from_json(fixture['auditRecords'][1])
    changes = record.changes
    assert isinstance(changes, tuple)


def test_change_roundtrip():
    """Verify Change serialization and deserialization."""
    change = Change(attribute='status', new_value='CLEARED', previous_value='ACTIVE', type='SomeType')
    j = change.to_json()
    assert j == {'attribute': 'status', 'newValue': 'CLEARED', 'previousValue': 'ACTIVE', 'type': 'SomeType'}

    restored = Change.from_json(j)
    assert restored.attribute == 'status'
    assert restored.new_value == 'CLEARED'
    assert restored.previous_value == 'ACTIVE'
    assert restored.type == 'SomeType'


def test_custom_fragment():
    """Verify that custom fragments are accessible via subscript."""
    fixture =load_sample_file("audit_records.json")
    record = AuditRecord.from_json(fixture['auditRecords'][3])
    assert record['c8y_Metadata']['action'] == 'SUBSCRIBE'
