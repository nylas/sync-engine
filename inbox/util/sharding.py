import random
from inbox.config import config


def generate_open_shard_key():
    """
    Return the key that can be passed into session_scope() for an open shard,
    picked at random.

    """
    shards = config.get_required('DATABASES')
    open_shards = [int(id_) for id_, params in shards.iteritems()
                   if params['OPEN']]

    # TODO[k]: Always pick min()instead?
    shard_id = random.choice(open_shards)
    key = shard_id << 48
    return key
