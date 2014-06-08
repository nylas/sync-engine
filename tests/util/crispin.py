# NOT a fixture because it needs args
def crispin_client(account_id, account_provider):
    from inbox.crispin import connection_pool
    return connection_pool(account_id, pool_size=1).get()
