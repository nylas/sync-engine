import datetime
from collections import defaultdict

'''
This file currently contains algorithms for the contacts/rankings endpoint
and the groups/intrinsic endpoint.
'''

# For calculating message weights
LOOKBACK_TIME = 63072000.0  # datetime.timedelta(days=2*365).total_seconds()
MIN_MESSAGE_WEIGHT = .01

# For calculate_group_scores
MIN_GROUP_SIZE = 2
MIN_MESSAGE_COUNT = 2.5  # Might want to tune this param. (1.5, 2.5?)
SELF_IDENTITY_THRESHOLD = 0.3  # Also tunable
JACCARD_THRESHOLD = .35  # probably shouldn't tune this

SOCIAL_MOLECULE_EXPANSION_LIMIT = 1000  # Don't add too many molecules!
SOCIAL_MOLECULE_LIMIT = 5000  # Give up if there are too many messages


##
# Helper functions
##


def _get_message_weight(now, message_date):
    timediff = now - message_date
    weight = 1 - (timediff.total_seconds() / LOOKBACK_TIME)
    return max(weight, MIN_MESSAGE_WEIGHT)


def _jaccard_similarity(set1, set2):
    return len(set1.intersection(set2)) / float(len(set1.union(set2)))


def _get_participants(msg, excluded_emails=[]):
    """Returns an alphabetically sorted list of
    emails addresses that msg was sent to (including cc and bcc)
    """
    participants = msg.to_addr + msg.cc_addr + msg.bcc_addr
    return sorted(list(set([email.lower() for _, email in participants
                            if email not in excluded_emails])))


# Not really an algorithm, but it seemed reasonable to put this here?
def is_stale(last_updated, lifespan=14):
    """ last_updated is a datetime.datetime object
        lifespan is measured in days
    """
    if last_updated is None:
        return True
    expiration_date = last_updated + datetime.timedelta(days=lifespan)
    return datetime.datetime.now() > expiration_date


##
# The actual algorithms for contact rankings and groupings!
##

def calculate_contact_scores(messages, time_dependent=True):
    now = datetime.datetime.now()
    res = defaultdict(int)
    for message in messages:
        if time_dependent:
            weight = _get_message_weight(now, message.date)
        else:
            weight = 1
        recipients = message.to_addr + message.cc_addr + message.bcc_addr
        for (name, email) in recipients:
            res[email] += weight
    return res


def calculate_group_counts(messages, user_email):
    """Strips out most of the logic from calculate_group_scores
    algorithm and just returns raw counts for each group.
    """
    res = defaultdict(int)
    for msg in messages:
        participants = _get_participants(msg, [user_email])
        if len(participants) >= MIN_GROUP_SIZE:
            res[', '.join(participants)] += 1
    return res


def calculate_group_scores(messages, user_email):
    """This is a (modified) implementation of the algorithm described
    in this paper: http://mobisocial.stanford.edu/papers/iui11g.pdf

    messages must have the following properties:
        to_addr - [('name1', 'email1@e.com'), ... ]
        cc_addr - [('name1', 'email1@e.com'), ... ]
        bcc_addr - [('name1', 'email1@e.com'), ... ]
        date - datetime.datetime object
    """
    now = datetime.datetime.now()
    message_ids_to_scores = {}
    molecules_dict = defaultdict(set)  # (emails, ...) -> {message ids, ...}

    def get_message_list_weight(message_ids):
        return sum([message_ids_to_scores[m_id] for m_id in message_ids])

    # Gather initial candidate social molecules
    for msg in messages:
        participants = _get_participants(msg, [user_email])
        if len(participants) >= MIN_GROUP_SIZE:
            molecules_dict[tuple(participants)].add(msg.id)
            message_ids_to_scores[msg.id] = \
                _get_message_weight(now, msg.date)

    if len(molecules_dict) > SOCIAL_MOLECULE_LIMIT:
        return {}  # Not worth the calculation

    # Expand pool of social molecules by taking pairwise intersections.
    # If there are already too many molecules, skip this step.
    if len(molecules_dict) < SOCIAL_MOLECULE_EXPANSION_LIMIT:
        _expand_molecule_pool(molecules_dict)

    # Filter out infrequent molecules
    molecules_list = [(set(emails), set(msgs))
                      for (emails, msgs) in molecules_dict.iteritems()
                      if get_message_list_weight(msgs) >= MIN_MESSAGE_COUNT]

    # Subsets get absorbed by supersets (if minimal info lost)
    molecules_list = _subsume_molecules(
        molecules_list, get_message_list_weight)

    molecules_list = _combine_similar_molecules(molecules_list)

    # Give a score to each group.
    return {', '.join(sorted(g)): get_message_list_weight(m)
            for (g, m) in molecules_list}


# Helper functions for calculating group scores
def _expand_molecule_pool(molecules_dict):
    mditems = [(set(g), msgs) for (g, msgs) in molecules_dict.items()]
    for i in xrange(len(mditems)):
        g1, m1 = mditems[i]
        for j in xrange(i, len(mditems)):
            g2, m2 = mditems[j]
            new_molecule = tuple(sorted(list(g1.intersection(g2))))
            if len(new_molecule) >= MIN_GROUP_SIZE:
                molecules_dict[new_molecule] = \
                        molecules_dict[new_molecule].union(m1).union(m2)


def _subsume_molecules(molecules_list, get_message_list_weight):
    molecules_list.sort(key=lambda x: len(x[0]), reverse=True)
    is_subsumed = [False] * len(molecules_list)
    mol_weights = [get_message_list_weight(m) for (_, m) in molecules_list]

    for i in xrange(1, len(molecules_list)):
        g1, m1 = molecules_list[i]  # Smaller group
        m1_size = mol_weights[i]
        for j in xrange(i):
            if is_subsumed[j]:
                continue
            g2, m2 = molecules_list[j]  # Bigger group
            m2_size = mol_weights[j]
            if g1.issubset(g2):
                sharing_error = ((len(g2) - len(g1)) * (m1_size - m2_size) /
                                 (1.0 * (len(g2) * m1_size)))
                if sharing_error < SELF_IDENTITY_THRESHOLD:
                    is_subsumed[i] = True
                    break

    return [ml for (ml, dead) in zip(molecules_list, is_subsumed) if not dead]


def _combine_similar_molecules(molecules_list):
    """Using a greedy approach here for speed"""
    new_guys_start_idx = 0
    while new_guys_start_idx < len(molecules_list):
        combined = [False] * len(molecules_list)
        new_guys = []
        for j in xrange(new_guys_start_idx, len(molecules_list)):
            for i in xrange(0, j):
                if combined[i]:
                    continue
                (g1, m1), (g2, m2) = molecules_list[i], molecules_list[j]
                js = _jaccard_similarity(g1, g2)
                if js > JACCARD_THRESHOLD:
                    new_guys.append((g1.union(g2), m1.union(m2)))
                    combined[i], combined[j] = True, True
                    break

        molecules_list = [molecule for molecule, was_combined
                          in zip(molecules_list, combined)
                          if not was_combined]
        new_guys_start_idx = len(molecules_list)
        molecules_list.extend(new_guys)

    return molecules_list
