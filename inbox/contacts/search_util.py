"""Utility functions to facilitate searching for contacts.

Contacts search looks a lot different from full-text search. 99% of the time
it's just prefix-matching. So we can provide a dead-simple but pretty effective
implementation.

To each Contact object we associate a set of search tokens. Right now these are
the contact's email address plus the elements of the contact's split name,
lowercased and stripped of punctuation. Given a search query string Q, a
contact is considered a result if it has a token T such that Q is a prefix of
T.
"""
from math import log

import sqlalchemy

from inbox.models import Contact, SearchSignal, SearchToken


def get_signal(contact, signal_name):
    signal = contact.search_signals.get(signal_name)
    if signal is not None:
        return signal.value
    else:
        return 0


def set_signal(contact, signal_name, new_value):
    """Update the search signal value with name signal_name for the given
    contact. Must be called within a db session."""
    signal = contact.search_signals.get(signal_name)
    if signal is not None:
        signal.value = new_value
    else:
        contact.search_signals[signal_name] = SearchSignal(name=signal_name,
                                                           value=new_value)


def increment_signal(contact, signal_name):
    """Increment the search signal value with name signal_name for the given
    contact. Must be called within a db session."""
    signal = contact.search_signals.get(signal_name)
    if signal is not None:
        signal.value += 1
    else:
        contact.search_signals[signal_name] = SearchSignal(name=signal_name,
                                                           value=1)


def update_timestamp_signal(contact, timestamp):
    """Helper function for updating the 'latest_timestamp' signal (the
    timestamp of the most recent email containing the given contact's email in
    the from/to/cc fields). Must be callend within a db session"""
    if get_signal(contact, 'latest_timestamp') < timestamp:
        set_signal(contact, 'latest_timestamp', timestamp)


def score(contact):
    """Update the contact's ranking score. Must be called within a db
    session."""
    to_count = get_signal(contact, 'to_count')
    from_count = get_signal(contact, 'from_count')
    cc_count = get_signal(contact, 'cc_count')
    bcc_count = get_signal(contact, 'bcc_count')
    # We're going to take the log, so this can't be zero.
    latest_ts = get_signal(contact, 'latest_timestamp') or 1

    # For now, just use this wild-guess heuristic.
    contact.score = int(to_count + 0.1 * from_count + 0.1 * cc_count +
                        0.1 * bcc_count + log(latest_ts, 10))
    # TODO(emfree): We should probably also:
    # * Penalize contacts that were scraped from mail data (and not synced from
    #   an actual contact list).
    # * Penalize contacts with low (read messages)/(unread messages) ratio.
    #   (Currently we don't track read status on the message object, making
    #   this nontrivial.)


def search(db_session, account_id, search_query, max_results, offset=0):
    query = db_session.query(Contact) \
        .filter(Contact.account_id == account_id,
                Contact.source == 'local',
                Contact.token.any(
                    SearchToken.token.startswith(search_query.lower()))) \
        .order_by(sqlalchemy.desc(Contact.score))
    if max_results > 0:
        query = query.limit(max_results)
    if offset:
        query = query.offset(offset)
    return query.all()
