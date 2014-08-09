
class BaseSyncProvider(object):
    def get(self, sync_from_time, max_results):
        raise NotImplementedError
