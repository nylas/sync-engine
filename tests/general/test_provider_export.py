from inbox.providers import providers
import json


def test_provider_export_as_json():
    """Provider dict should be exportable as json"""
    assert json.dumps(dict(providers))
