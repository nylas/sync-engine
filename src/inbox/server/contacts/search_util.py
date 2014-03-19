"""Utility functions to facilitate searching for contacts.

Contacts search looks a lot different from full-text search. 99% of the time
it's just prefix-matching. So we can provide a dead-simple but pretty effective
implementation.

To each Contact object we associate a set of search tokens. Right now these are
the contact's email address plus the elements of the contact's split name,
lowercased and stripped of punctuation. Given a search query string Q, a
contact is considered a result if it has a token T such that Q is a prefix of
T."""

from inbox.server.models.tables.base import Contact, SearchToken


def rank_search_results(results):
    # For now, just sort alphabetically by name.
    return sorted(results, lambda lhs, rhs: cmp(lhs.name, rhs.name))


def search(db_session, account_id, search_query, max_results):
    query = db_session.query(Contact) \
        .filter(Contact.account_id == account_id,
                Contact.source == 'local',
                Contact.token.any(
                    SearchToken.token.startswith(search_query.lower())))
    if max_results > 0:
        query = query.limit(max_results)
    return rank_search_results(query.all())
