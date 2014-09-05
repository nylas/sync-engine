from conftest import API_BASE
from inbox import APIClient


class InboxTestClient(APIClient):

    def __init__(self, email_address=None):
        self.email_address = email_address
        APIClient.__init__(self, None, None, None, API_BASE)

    @property
    def namespaces(self):
        all_ns = super(InboxTestClient, self).namespaces
        if self.email_address:
            return all_ns.where(email_address=self.email_address)
        else:
            return all_ns
