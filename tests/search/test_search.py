# import datetime
import json

from gevent import monkey
from pytest import yield_fixture, fixture

from inbox.models.message import Message
from inbox.search.adaptor import NamespaceSearchEngine
from inbox.search.util import index_namespaces
# from inbox.util.misc import dt_to_timestamp


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

@fixture
def message(db):
    message = db.session.query(Message).get(2)
    return message

MESSAGE_ENDPOINT = '/messages/search'

# ## Validation tests


def test_message_search_or_all_fails(api_client):
    # Test that if we are searching across a list of queries (i.e. OR-ing them)
    # having an 'all' as one of those queries fails.
    data = dict(query=[{'subject': 'test'}, {'all': 'test'}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 400


def test_message_search_invalid_fieldname(api_client, search_engine):
    # Test that if we provide an invalid fieldname the API rejects the query
    data = dict(query=[{'abracadabra': 'kapow'}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 400

    # Test that if we provide a thread-property fieldname the API accepts it
    data = dict(query=[{'participants': 'blah'}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200


def test_message_search_invalid_sort(api_client):
    # Test that if we provide an invalid sort type the API rejects the query
    data = dict(query=[{'subject': 'test'}], sort='backward')
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 400

# ## Behaviour tests


def test_message_search_all(db, api_client, search_engine, message):
    # No query i.e. return all
    resp = api_client.post_data(MESSAGE_ENDPOINT, {})
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    total = result_dict['total']
    results = result_dict['results']
    assert total == 16 and len(results) == 16
    third_msg_id = results[2]['object']['id']

    # Test with limit and offset
    resp = api_client.post_data(MESSAGE_ENDPOINT + '?limit={}&offset={}'.
                                format(2, 2), {})
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    total = result_dict['total']
    results = result_dict['results']
    assert total > 2 and len(results) == 2
    assert results[0]['object']['id'] == third_msg_id


def test_message_search_thread_id(db, api_client, search_engine, message):
    # Simple field matching
    data = dict(query=[{'thread_id': message.thread.public_id}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_message_search_cc(db, api_client, search_engine, message):
    data = dict(query=[{'cc': message.cc_addr[0][1]}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_message_search_bcc(db, api_client, search_engine, message):
    data = dict(query=[{'bcc': ''}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 0


def test_message_search_from(db, api_client, search_engine, message):
    data = dict(query=[{'from': message.from_addr[0][1]}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_message_search_from_token(db, api_client, search_engine):
    # Test that an email address is matched appropriately based purely on
    # the domain. (Currently *not* sub-tokenized into matching 'spang' - TODO)
    data = dict(query=[{'from': 'spang.cc'}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_message_search_subject(db, api_client, search_engine, message):
    data = dict(query=[{'subject': message.subject}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_message_search_from_to(db, api_client, search_engine, message):
    data = dict(query=[{
        'from': message.from_addr[0][1],
        'to': message.to_addr[0][1]}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_message_search_field_limit(db, api_client, search_engine, message):
    data = dict(query=[{'to': 'inboxapptest@gmail.com'}])
    resp = api_client.post_data(MESSAGE_ENDPOINT + '?limit={}&offset={}'.
                                format(2, 1), data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 2


def test_message_search_body(db, api_client, search_engine, message):
    # Basic body matching (we expect a result for either phrase or token match)
    data = dict(query=[{'body': 'Google Search'}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_message_search_body_tokenized(db, api_client, search_engine, message):
    # Test that we get a body match and automatically tokenize this query
    data = dict(query=[{'body': 'reproduce paste'}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_message_search_all_simple(db, api_client, search_engine, message):
    # All fields, simple one-word match:
    data = dict(query=[{'all': 'yoga'}], sort='relevance')
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    default_results = result_dict['results']
    assert len(default_results) >= 5

    default = [(r['object']['id'], r['relevance']) for r in default_results]

    # All fields but with a boosting weight
    data = dict(query=[{'all': 'yoga', 'weights': {'from': 2}}],
                sort='relevance')
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    rescored_results = result_dict['results']
    assert len(rescored_results) >= 5

    rescored = [(r['object']['id'], r['relevance']) for r in rescored_results]

    assert rescored != default


def test_message_search_filename(db, api_client, search_engine, message):
    # Test that we get a filename match
    data = dict(query=[{'files': 'profilephoto.png'}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_message_search_numeric(db, api_client, search_engine):
    # Test that a numeric query works
    data = dict(query=[{'body': 1600}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 2

THREAD_ENDPOINT = '/threads/search'


# ## Validation tests

def test_thread_search_or_all_fails(api_client):
    # Test that if we are searching across a list of queries (i.e. OR-ing them)
    # having an 'all' as one of those queries fails.
    data = dict(query=[{'subject': 'test'}, {'all': 'test'}])
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 400


def test_thread_search_invalid_fieldname(api_client, search_engine):
    # Test that if we provide an invalid fieldname the API rejects the query
    data = dict(query=[{'abracadabra': 'kapow'}])
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 400

    # Test that if we provide a message-property fieldname the API accepts it
    data = dict(query=[{'bcc': 'blah'}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200


def test_thread_search_invalid_sort(api_client):
    # Test that if we provide an invalid sort type the API rejects the query
    data = dict(query=[{'subject': 'test'}], sort='backward')
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 400


def test_thread_search_invalid_combo(api_client):
    # We can't combine thread-level and non-thread-level queries (yet)
    data = dict(query=[{'subject': 'test', 'body': 'something'}])
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 501

    # We can't combine all and non-thread-level queries (yet)
    data = dict(query=[{'all': 'test', 'body': 'something'}])
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 501


# ## Behaviour tests

def test_thread_search_empty(db, api_client, search_engine, message):
    # No query i.e. return all
    resp = api_client.post_data(THREAD_ENDPOINT, {})
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    total = result_dict['total']
    results = result_dict['results']
    assert total == 16 and len(results) == 16


def test_thread_search_id(db, api_client, search_engine, message):
    # Simple field match-phrase queries:
    data = dict(query=[{'id': message.thread.public_id}])
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_thread_search_subject(db, api_client, search_engine, message):
    data = dict(query=[{'subject': message.thread.subject}])
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_thread_search_tags(db, api_client, search_engine, message):
    data = dict(query=[{'tags': 'inbox'}])
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 10


def test_thread_search_limited(db, api_client, search_engine):
    data = dict(query=[{'tags': 'inbox'}])
    resp = api_client.post_data(THREAD_ENDPOINT + '?limit={}'.format(1), data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    total = result_dict['total']
    results = result_dict['results']
    assert total > 1 and len(results) == 1


def test_thread_search_participants(db, api_client, search_engine):
    # Test that we pick up participants matches without needing the exact
    # phrase to match. The 'participants' data for this name is stored as
    # Paul X. Tiseo.
    data = dict(query=[{'participants': 'paul tiseo'}])
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_thread_search_all(db, api_client, search_engine):
    # Test that we search nested fields (participants, etc)
    # during thread 'all' search
    data = dict(query=[{'all': 'tiseo'}])
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


def test_thread_search_weight(db, api_client, search_engine):
    # Test that we get different results if specifying weights.
    data = dict(query=[{'all': 'ben'}], sort='relevance')
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 6
    default = [(r['object']['id'], r['relevance']) for r in results]

    # Now weight the same query towards 'body'
    data = dict(query=[{'all': 'ben', 'weights': {'body': 3}}],
                sort='relevance')
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 6
    rescored = [(r['object']['id'], r['relevance']) for r in results]

    assert default != rescored

    # TODO[k]:
    # Dates
    # t_start = dt_to_timestamp(thread.subjectdate)
    # t_lastmsg = dt_to_timestamp(thread.recentdate)


# ## Query composition tests

def test_or_search(db, api_client, search_engine):
    # Test an OR query with messages
    data = dict(query=[{'from': 'ben'}, {'from': 'kavya'}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    results = json.loads(resp.data)['results']
    assert len(results) == 7


def test_parent_child_search(db, api_client, search_engine, message):
    # Messages via querying thread-level field:
    data = dict(query=[{'tags': 'inbox'}])
    resp = api_client.post_data(MESSAGE_ENDPOINT, data)
    assert resp.status_code == 200
    results = json.loads(resp.data)['results']
    assert len(results) == 10

    # Threads via querying a field that only exists on message:
    data = dict(query=[{'body': 'reproduce paste'}])
    resp = api_client.post_data(THREAD_ENDPOINT, data)
    assert resp.status_code == 200
    result_dict = json.loads(resp.data)
    results = result_dict['results']
    assert len(results) == 1


# ## Consistency tests

def test_search_response(db, api_client, search_engine):
    # Test that the data returned from search matches the data returned
    # by the API.
    resp = api_client.post_data(MESSAGE_ENDPOINT + '?limit={}&offset={}'.
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

    resp = api_client.post_data(THREAD_ENDPOINT + '?limit={}&offset={}'.
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
