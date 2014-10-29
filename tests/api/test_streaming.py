import json
import pytest
from sqlalchemy import asc, desc
from tests.util.base import api_client, default_namespace
from inbox.models import Transaction, Namespace
from inbox.util.url import url_concat


@pytest.yield_fixture
def streaming_test_client(db):
    from inbox.api.srv import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def api_prefix(default_namespace):
    return '/n/{}/delta/streaming'.format(default_namespace.public_id)


def test_empty_response_when_no_changes(streaming_test_client, api_prefix):
    url = url_concat(api_prefix, {'timeout': .1})
    r = streaming_test_client.get(url)
    assert r.status_code == 200
    assert r.data == ''


def test_response_when_cursor_given(db, api_prefix, streaming_test_client,
                                    default_namespace):
    old_transaction = db.session.query(Transaction).filter(
        Transaction.namespace_id == default_namespace.id). \
        order_by(asc(Transaction.id)).first()
    url = url_concat(api_prefix, {'timeout': .1,
                                  'cursor': old_transaction.public_id})
    r = streaming_test_client.get(url)
    assert r.status_code == 200
    assert json.loads(r.data) == {'namespace_id': default_namespace.public_id}


def test_empty_response_when_latest_cursor_given(db, api_prefix,
                                                 streaming_test_client,
                                                 default_namespace):
    newest_transaction = db.session.query(Transaction).filter(
        Transaction.namespace_id == default_namespace.id). \
        order_by(desc(Transaction.id)).first()
    url = url_concat(api_prefix, {'timeout': .1,
                                  'cursor': newest_transaction.public_id})
    r = streaming_test_client.get(url)
    assert r.status_code == 200
    assert r.data == ''


def test_gracefully_handle_no_transactions(db, streaming_test_client):
    new_namespace = Namespace()
    db.session.add(new_namespace)
    db.session.commit()
    url = url_concat('/n/{}/delta/streaming'.format(new_namespace.public_id),
                     {'timeout': .1})
    r = streaming_test_client.get(url)
    assert r.status_code == 200
    assert r.data == ''
