
class BaseSyncProvider(object):
    def get(self, sync_from_time):
        raise NotImplementedError
