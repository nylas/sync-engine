import json
import pytest
from inbox.mailsync.frontend import HTTPFrontend
from inbox.mailsync.service import SyncService


@pytest.yield_fixture
def mailsync_frontend():
    s = SyncService('localhost:0', 0)
    frontend = HTTPFrontend(s, 16384, False, False)
    app = frontend._create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_account_state_updated(default_account, db, mailsync_frontend):
    default_account.sync_host = 'localhost:0'
    db.session.commit()
    resp = mailsync_frontend.post(
        '/unassign', data=json.dumps({'account_id': default_account.id}),
        content_type='application/json')
    assert resp.status_code == 200
    db.session.expire_all()
    assert default_account.sync_host is None


def test_account_state_not_updated_on_conflict(default_account, db,
                                               mailsync_frontend):
    default_account.sync_host = 'localhost:22'
    db.session.commit()
    resp = mailsync_frontend.post(
        '/unassign', data=json.dumps({'account_id': default_account.id}),
        content_type='application/json')
    assert resp.status_code == 409
    db.session.expire_all()
    assert default_account.sync_host == 'localhost:22'
