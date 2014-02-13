# NOT a fixture because it needs args
def crispin_client(account_id, account_provider):
    from inbox.server.crispin import new_crispin
    return new_crispin(account_id, account_provider, conn_pool_size=1)
