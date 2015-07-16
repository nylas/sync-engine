def get_search_client(account):
    from inbox.search.backends import module_registry

    search_mod = module_registry.get(account.provider)
    search_cls = getattr(search_mod, search_mod.SEARCH_CLS)
    search_client = search_cls(account)
    return search_client
