import json
from inbox.models import DataProcessingCache
from sqlalchemy.orm.exc import NoResultFound
from tests.util.base import (api_client, add_fake_thread,
                             add_fake_message, default_namespace)


__all__ = ['api_client', 'default_namespace']


def test_contact_rankings(db, api_client, default_namespace):
    # Clear cached data (if it exists)
    namespace_id = default_namespace.id
    try:
        cached_data = db.session.query(DataProcessingCache) \
                      .filter(DataProcessingCache.namespace_id ==
                              namespace_id).one()
        cached_data.contact_rankings_last_updated = None
        db.session.add(cached_data)
        db.session.commit()
    except NoResultFound:
        pass

    # Send some emails
    namespace_email = default_namespace.email_address

    me = ('me', namespace_email)
    recipients = ([[('first', 'number1@nylas.com')]] * 8 +
                  [[('second', 'number2@nylas.com')]] * 4 +
                  [[('third', 'number3@nylas.com')]] +
                  [[('third', 'number3@nylas.com'),
                    ('fourth', 'number4@nylas.com')]])

    for recipients_list in recipients:
        fake_thread = add_fake_thread(db.session, namespace_id)
        add_fake_message(db.session, namespace_id, fake_thread,
                         subject='Froop',
                         from_addr=[me],
                         to_addr=recipients_list)

    db.session.commit()

    # Check contact rankings
    resp = api_client.client.get(api_client.full_path(
        '/contacts/rankings?force_recalculate=true'))
    assert resp.status_code == 200

    emails_scores = {e: s for (e, s) in json.loads(resp.data)}
    emails = ['number1@nylas.com', 'number2@nylas.com',
              'number3@nylas.com', 'number4@nylas.com']
    for email in emails:
        assert email in emails_scores

    for e1, e2 in zip(emails, emails[1:]):
        assert emails_scores[e1] > emails_scores[e2]

    # make sure it works if we call it again!
    resp = api_client.client.get(api_client.full_path(
        '/contacts/rankings'))
    assert resp.status_code == 200

    emails_scores = {e: s for (e, s) in json.loads(resp.data)}
    emails = ['number1@nylas.com', 'number2@nylas.com',
              'number3@nylas.com', 'number4@nylas.com']
    for email in emails:
        assert email in emails_scores

    for e1, e2 in zip(emails, emails[1:]):
        assert emails_scores[e1] > emails_scores[e2]

    try:
        cached_data = db.session.query(DataProcessingCache) \
                      .filter(DataProcessingCache.namespace_id ==
                              namespace_id).one()
        assert cached_data.contact_rankings_last_updated is not None
    except (NoResultFound, AssertionError):
        assert False, "Contact rankings not cached"


def test_contact_groups(db, api_client, default_namespace):
    # Clear cached data (if it exists)
    namespace_id = default_namespace.id
    try:
        cached_data = db.session.query(DataProcessingCache) \
                      .filter(DataProcessingCache.namespace_id ==
                              namespace_id).one()
        cached_data.contact_groups_last_updated = None
        db.session.add(cached_data)
        db.session.commit()
    except NoResultFound:
        pass

    # Send some emails
    namespace_email = default_namespace.email_address
    me = ('me', namespace_email)
    recipients = ([[('a', 'a@nylas.com'),
                   ('b', 'b@nylas.com'),
                   ('c', 'c@nylas.com')]] * 8 +
                  [[('b', 'b@nylas.com'),
                     ('c', 'c@nylas.com'),
                     ('d', 'd@nylas.com')]] * 8 +
                  [[('d', 'd@nylas.com'),
                     ('e', 'e@nylas.com'),
                     ('f', 'f@nylas.com')]] * 8 +
                  [[('g', 'g@nylas.com'),
                     ('h', 'h@nylas.com'),
                     ('i', 'i@nylas.com'),
                     ('j', 'j@nylas.com')]] * 5 +
                   [[('g', 'g@nylas.com'),
                     ('h', 'h@nylas.com'),
                     ('i', 'i@nylas.com')]] * 2 +
                  [[('k', 'k@nylas.com'),
                     ('l', 'l@nylas.com')]] * 3)

    for recipients_list in recipients:
        fake_thread = add_fake_thread(db.session, namespace_id)
        add_fake_message(db.session, namespace_id, fake_thread,
                         subject='Froop',
                         from_addr=[me],
                         to_addr=recipients_list)

    db.session.commit()

    # Check contact groups
    resp = api_client.client.get(api_client.full_path(
        '/groups/intrinsic?force_recalculate=true'))
    assert resp.status_code == 200

    groups_scores = {g: s for (g, s) in json.loads(resp.data)}
    groups = ['a@nylas.com, b@nylas.com, c@nylas.com, d@nylas.com',
              'd@nylas.com, e@nylas.com, f@nylas.com',
              'g@nylas.com, h@nylas.com, i@nylas.com, j@nylas.com',
              'k@nylas.com, l@nylas.com']
    for g in groups:
        assert g in groups_scores

    # make sure it works when we do it again
    resp = api_client.client.get(api_client.full_path(
        '/groups/intrinsic'))
    assert resp.status_code == 200

    groups_scores = {g: s for (g, s) in json.loads(resp.data)}
    for g in groups:
        assert g in groups_scores

    try:
        cached_data = db.session.query(DataProcessingCache) \
                      .filter(DataProcessingCache.namespace_id ==
                              namespace_id).one()
        assert cached_data.contact_groups_last_updated is not None
    except (NoResultFound, AssertionError):
        assert False, "Contact groups not cached"
