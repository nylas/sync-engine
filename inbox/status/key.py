class SyncStatusKey(object):
    def __init__(self, account_id, folder_id):
        self.account_id = account_id
        self.folder_id = folder_id
        self.key = '{}:{}'.format(self.account_id, self.folder_id)

    def __repr__(self):
        return self.key

    def __lt__(self, other):
        if self.account_id != other.account_id:
            return self.account_id < other.account_id
        return self.folder_id < other.folder_id

    def __le__(self, other):
        if self.account_id != other.account_id:
            return self.account_id < other.account_id
        return self.folder_id <= other.folder_id

    def __eq__(self, other):
        return self.account_id == other.account_id and \
            self.folder_id == other.folder_id

    def __ne__(self, other):
        return self.account_id != other.account_id or \
            self.folder_id != other.folder_id

    def __gt__(self, other):
        if self.account_id != other.account_id:
            return self.account_id > other.account_id
        return self.folder_id > other.folder_id

    def __ge__(self, other):
        if self.account_id != other.account_id:
            return self.account_id > other.account_id
        return self.folder_id >= other.folder_id

    @classmethod
    def all_folders(cls, account_id):
        return cls(account_id, '*')

    @classmethod
    def from_string(cls, string_key):
        account_id, folder_id = map(int, string_key.split(':'))
        return cls(account_id, folder_id)
