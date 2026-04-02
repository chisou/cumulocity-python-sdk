# Copyright (c) 2025 Cumulocity GmbH

import json
import os

from pyc8y.model.application import Application


def test_parsing():
    """Verify that parsing an Application from JSON works."""
    path = os.path.dirname(__file__) + '/application.json'
    with open(path, encoding='utf-8', mode='rt') as f:
        application_json = json.load(f)
    application = Application.from_json(application_json)

    assert application.id == application_json['id']
    assert application.name == application_json['name']
    assert application.key == application_json['key']
    assert application.type == application_json['type']
    assert application.availability == application_json['availability']
    assert application.context_path == application_json['contextPath']
    assert application.active_version_id == application_json['activeVersionId']
    assert application.owner == application_json['owner']['tenant']['id']
