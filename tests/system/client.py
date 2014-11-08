import os
from inbox import APIClient


class InboxTestClient(APIClient):

    def __init__(self, email_address=None, api_base=os.getenv("INBOX_API_PORT_5555_TCP_ADDR","http://localhost:5555")):
        self.email_address = email_address
        APIClient.__init__(self, None, None, None, api_base)

    @property
    def namespaces(self):
        all_ns = super(InboxTestClient, self).namespaces
        if self.email_address:
            return all_ns.where(email_address=self.email_address)
        else:
            return all_ns
