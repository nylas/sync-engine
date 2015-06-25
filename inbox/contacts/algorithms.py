import datetime
from collections import defaultdict
from itertools import combinations

'''
This file currently contains algorithms for the contacts/rankings endpoint
and the groups/intrinsic endpoint.
'''

# For calculating message weights
LOOKBACK_TIME = 63072000.0  # datetime.timedelta(days=2*365).total_seconds()
MIN_MESSAGE_WEIGHT = .01

# For calculate_group_scores
MIN_GROUP_SIZE = 2
MIN_MESSAGE_COUNT = 1.5  # Might want to tune this param. (2.5?)
SELF_IDENTITY_THRESHOLD = 0.3  # Also tunable
JACCARD_THRESHOLD = .35  # probably shouldn't tune this

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
    """This is an implementation of the algorithm described
    in this paper: http://mobisocial.stanford.edu/papers/iui11g.pdf

    messages must have the following properties:
        to_addr - [('name1', 'email1@e.com'), ... ]
        cc_addr - [('name1', 'email1@e.com'), ... ]
        bcc_addr - [('name1', 'email1@e.com'), ... ]
        date - datetime.datetime object
    """
    now = datetime.datetime.now()
    message_ids_to_scores = {}
    # molecules_dict maps (tuple of emails,) -> [list of message ids]
    molecules_dict = defaultdict(set)

    def get_message_list_weight(message_ids):
        return sum([message_ids_to_scores[m_id] for m_id in message_ids])

    # STEP 1: Gather initial candidate social molecules
    for msg in messages:
        participants = _get_participants(msg, [user_email])
        if len(participants) >= MIN_GROUP_SIZE:
            molecules_dict[tuple(participants)].add(msg.id)
            message_ids_to_scores[msg.id] = \
                _get_message_weight(now, msg.date)

    # STEP 2: Expand pool of social molecules by taking pairwise intersections.
    new_guys = [1]  # random filler, because python has no do...while loop
    while len(new_guys) > 0:
        new_guys = {}
        for ((g1, m1), (g2, m2)) in combinations(molecules_dict.items(), 2):
            new_set = set(g1).intersection(set(g2))
            new_molecule = tuple(sorted(list(new_set)))
            if len(new_molecule) >= MIN_GROUP_SIZE:
                if new_molecule not in molecules_dict:
                    if new_molecule in new_guys:
                        # update the messages!
                        new_guys[new_molecule] = \
                            new_guys[new_molecule].union(m1).union(m2)
                    else:
                        new_guys[new_molecule] = m1.union(m2)
                else:
                    # update the messages!
                    molecules_dict[new_molecule] = \
                        molecules_dict[new_molecule].union(m1).union(m2)
        molecules_dict.update(new_guys)

    # STEP 3: Filter out infrequent molecules
    molecules_list = [(set(emails), set(msgs))
                      for (emails, msgs) in molecules_dict.iteritems()
                      if get_message_list_weight(msgs) >= MIN_MESSAGE_COUNT]

    # STEP 4: Test each molecule to see if it can be subsumed by a
    #         superset molecule (with minimal information loss)

    # sort by number of participants
    molecules_list.sort(key=lambda x: len(x[0]), reverse=True)
    if len(molecules_list) == 0:
        return {}
    surviving_molecules = [molecules_list[0]]
    subsumed = set()    # Keep track of indices of subsumed molecules

    for i in xrange(1, len(molecules_list)):
        is_subsumed = False
        g1, m1 = molecules_list[i]  # Smaller group
        m1_size = get_message_list_weight(m1)

        for j in xrange(i):
            if j in subsumed:
                continue

            g2, m2 = molecules_list[j]  # Bigger group
            m2_size = get_message_list_weight(m2)
            if g1.issubset(g2):
                # Sharing error
                serr = ((len(g2) - len(g1)) * (m1_size - m2_size) /
                        (1.0 * (len(g2) * m1_size)))
                if serr < SELF_IDENTITY_THRESHOLD:
                    subsumed.add(i)
                    is_subsumed = True
                    break
        if not is_subsumed:
            surviving_molecules.append(molecules_list[i])

    molecules_list = surviving_molecules

    # STEP 5: Merge similar molecules
    # best = float('infinity')
    # while best > JACCARD_THRESHOLD:
    #     best = -float('infinity')
    #     best_values = None

    #     for ((g1, m1), (g2, m2)) in combinations(molecules_list, 2):
    #         js = _jaccard_similarity(g1, g2)
    #         if js > best:
    #             best = js
    #             best_values = (g1, m1), (g2, m2)

    #     if best > JACCARD_THRESHOLD:
    #         (g1, m1), (g2, m2) = best_values
    #         molecules_list.remove((g1, m1))
    #         molecules_list.remove((g2, m2))
    #         molecules_list.append((g1.union(g2), m1.union(m2)))

    # ALTERNATE STEP 5: Considerably more performant
    # Old version: iteratively combine best pair. Once combined,
    #              had to recalculate all pairs to find new best
    # New version: calculate score for each pair, then combine
    #              all pairs that meet the threshold on each step,
    #              starting from the highest-scoring pair.
    new_guys = [1]
    while len(new_guys) > 0:
        combined = [False] * len(molecules_list)
        scores_combo_idxs = []
        new_guys = []

        for (i, j) in combinations(xrange(len(molecules_list)), 2):
            (g1, m1), (g2, m2) = molecules_list[i], molecules_list[j]
            js = _jaccard_similarity(g1, g2)
            scores_combo_idxs.append((js, (i, j)))

        for (score, (i, j)) in sorted(scores_combo_idxs, reverse=True):
            if score < JACCARD_THRESHOLD:
                break   # score < threshold for all to follow
            if not combined[i] and not combined[j]:
                (g1, m1), (g2, m2) = molecules_list[i], molecules_list[j]
                new_guys.append((g1.union(g2), m1.union(m2)))
                combined[i], combined[j] = True, True

        molecules_list = [molecule for molecule, was_combined
                          in zip(molecules_list, combined)
                          if not was_combined]
        molecules_list.extend(new_guys)

    # STEP 6: Give a score to each group.
    return {', '.join(sorted(g)): get_message_list_weight(m)
            for (g, m) in molecules_list}


# Not really an algorithm, but it seemed reasonable to put this here?
def is_stale(last_updated, lifespan=14):
    """ last_updated is a datetime.datetime object
        lifespan is measured in days
    """
    if last_updated is None:
        return True
    expiration_date = last_updated + datetime.timedelta(days=lifespan)
    return datetime.datetime.now() > expiration_date
