#import datetime
import json

from gevent import monkey
from pytest import yield_fixture

from inbox.models.message import Message
from inbox.search.adaptor import NamespaceSearchEngine
from inbox.search.util import index_namespaces
#from inbox.util.misc import dt_to_timestamp


@yield_fixture(scope='function')
def search_index_service(db):
    # Based on the syncback_service fixture in tests/util/base.
    monkey.patch_all(aggressive=False)
    from inbox.transactions.search import SearchIndexService
    s = SearchIndexService(poll_interval=0.1)
    s.start()
    yield s


@yield_fixture(scope='function')
def search_engine(db, default_namespace):
    index_namespaces([default_namespace.id])

    engine = NamespaceSearchEngine(default_namespace.public_id,
                                   create_index=True)
    engine.refresh_index()

    yield engine

    engine.delete_index()


# TODO[k]
# def test_search_index_service(search_index_service, db, default_namespace,
#                               api_client):
#     from inbox.models import Transaction

#     sleep(5)

#     q = db.session.query(Transaction).filter(
#         Transaction.namespace_id == default_namespace.id)

#     message_count = q.filter(Transaction.object_type == 'message').count()
#     thread_count = q.filter(Transaction.object_type == 'thread').count()

#     resp = api_client.post_data('/messages/search', {})
#     assert resp.status_code == 200
#     results = json.loads(resp.data)
#     assert len(results) == message_count

#     resp = api_client.post_data('/threads/search', {})
#     assert resp.status_code == 200
#     results = json.loads(resp.data)
#     assert len(results) == thread_count


def test_message_search(db, api_client, search_engine):
    message = db.session.query(Message).get(2)

    subject = message.subject
    to_addr = message.to_addr[0][1]
    from_addr = message.from_addr[0][1]
    cc_addr = message.cc_addr[0][1]
    bcc_addr = message.bcc_addr
    #received_date = message.received_date

    endpoint = '/messages/search'

    # No query i.e. return all
    resp = api_client.post_data(endpoint, {})
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    total = result_dict['total']
    results = result_dict['results']
    assert total == 16 and len(results) == 16
    third_msg_id = results[2]['object']['id']

    resp = api_client.post_data(endpoint + '?limit={}&offset={}'.
                                format(2, 2), {})
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    total = result_dict['total']
    results = result_dict['results']
    assert total > 2 and len(results) == 2
    assert results[0]['object']['id'] == third_msg_id

    # Simple field match-phrase queries:
    data = dict(query=[{'thread_id': 'e6z26rjrxs2gu8at6gsa8svr1'}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1

    data = dict(query=[{'cc': cc_addr}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1

    data = dict(query=[{'bcc': bcc_addr}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 0

    data = dict(query=[{'from': from_addr}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1

    data = dict(query=[{'subject': subject}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1

    data = dict(query=[{
        'from': from_addr,
        'to': to_addr}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1

    data = dict(query=[{'to': 'inboxapptest@gmail.com'}])
    resp = api_client.post_data(endpoint + '?limit={}&offset={}'.
                                format(2, 1), data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 2

    data = dict(query=[{'body': 'Google Search'}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1

    # Simple field match queries:
    data = dict(query=[{'body': 'reproduce paste'}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    match_phrase_results = result_dict['results']

    data = dict(query=[{'body': ['reproduce', 'paste']}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    match_results = result_dict['results']

    assert len(match_phrase_results) == 0 and len(match_results) == 1

    # All fields, match-phrase query:
    data = dict(query=[{'all': 'yoga'}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    default_results = result_dict['results']
    assert len(default_results) >= 5

    default = [(r['object']['id'], r['relevance']) for r in default_results]

    data = dict(query=[{'all': 'yoga', 'weights': {'from': 2}}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    rescored_results = result_dict['results']
    assert len(rescored_results) >= 5

    rescored = [(r['object']['id'], r['relevance']) for r in rescored_results]

    assert rescored != default

    # TODO[k]: These too
    # results = api_client.get_data('/messages?filename=test')
    # assert len(results) == 0

    # Dates


def test_thread_search(db, api_client, search_engine):
    message = db.session.query(Message).filter_by(id=2).one()
    thread = message.thread

    subject = thread.subject
    #t_start = dt_to_timestamp(thread.subjectdate)
    #t_lastmsg = dt_to_timestamp(thread.recentdate)

    endpoint = '/threads/search'

    # No query i.e. return all
    resp = api_client.post_data(endpoint, {})
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    total = result_dict['total']
    results = result_dict['results']
    assert total == 16 and len(results) == 16

    # Simple field match-phrase queries:
    data = dict(query=[{'id': 'e6z26rjrxs2gu8at6gsa8svr1'}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1

    data = dict(query=[{'subject': subject}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1

    data = dict(query=[{'tags': 'inbox'}])
    resp = api_client.post_data(endpoint, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 10

    data = dict(query=[{'tags': 'inbox'}])
    resp = api_client.post_data(endpoint + '?limit={}'.format(1), data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    total = result_dict['total']
    results = result_dict['results']
    assert total > 1 and len(results) == 1

    # TODO[k]:
    # Different weights
    # Dates


# TODO[k]
#def test_parent_child_search(db, api_client, search_engine):
    # message = db.session.query(Message).get(2)
    # from_addr = message.from_addr[0][1]

    # # Messages via //thread// field match-phrase query:
    # endpoint = '/messages/search'
    # data = dict(query=[{'tags': 'inbox'}])
    # resp = api_client.post_data(endpoint, data)
    # assert resp.status_code == 200
    # results = json.loads(resp.data)
    # assert len(results) == 10

    # # Threads via //message// field match-phrase query:
    # endpoint = '/threads/search'
    # data = dict(query=[{'from': from_addr}])
    # resp = api_client.post_data(endpoint, data)
    # assert resp.status_code == 200
    # results = json.loads(resp.data)
    # assert len(results) == 1


# TODO[k]
def test_validation(db, api_client, search_engine):
    pass


def test_search_response(db, api_client, search_engine):
    endpoint = '/messages/search'
    resp = api_client.post_data(endpoint + '?limit={}&offset={}'.
                                format(1, 0), {})
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1

    search_repr = results[0]['object']
    message_id = search_repr['id']

    api_repr = api_client.get_data('/messages/{}'.format(message_id))

    assert search_repr['to'] == api_repr['to']
    assert search_repr['from'] == api_repr['from']
    assert search_repr['cc'] == api_repr['cc']
    assert search_repr['bcc'] == api_repr['bcc']
    assert search_repr['files'] == api_repr['files']

    endpoint = '/threads/search'
    resp = api_client.post_data(endpoint + '?limit={}&offset={}'.
                                format(1, 0), {})
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1

    search_repr = results[0]['object']
    thread_id = search_repr['id']

    api_repr = api_client.get_data('/threads/{}'.format(thread_id))

    assert sorted(search_repr['tags']) == sorted(api_repr['tags'])
    assert search_repr['participants'] == api_repr['participants']
