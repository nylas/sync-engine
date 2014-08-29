import requests
import json
from collections import namedtuple
from conftest import API_BASE


class InboxAPIObject(dict):
    attrs = []

    def __init__(self):
        self.dct = {}

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    @classmethod
    def from_dict(cls, dct):
        obj = cls()
        for attr in cls.attrs:
            if attr in dct:
                obj[attr] = dct[attr]

        return obj


class Message(InboxAPIObject):
    attrs = ["bcc", "body", "date", "file_ids", "from", "id", "namespace_id",
             "object", "subject", "thread_id", "to", "unread"]


class Tag(InboxAPIObject):
    attrs = ["id", "name", "namespace_id", "object"]


class Thread(InboxAPIObject):
    attrs = ["draft_ids", "id", "message_ids", "namespace_id", "object",
             "participants", "snippet", "subject", "subject_date", "tags"]


class Draft(InboxAPIObject):
    attrs = Message.attrs + ["state", "version"]


class File(InboxAPIObject):
    attrs = ["content_type", "filename", "id", "is_embedded", "message_id",
             "namespace_id", "object", "size"]


class Event(InboxAPIObject):
    attrs = ["id", "namespace_id", "subject", "body", "location", "read_only",
             "start", "end", "participants"]


class Namespace(InboxAPIObject):
    attrs = ["account_id", "email_address", "id", "namespace_id", "object",
             "provider"]


class APIClient(object):
    """A basic client for the Inbox API."""
    apiBase = API_BASE
    Message = namedtuple('Message', 'id thread')

    @classmethod
    def namespaces(cls):
        r = requests.get(cls.apiBase)
        return r.json()

    @classmethod
    def from_email(cls, email_address):
        namespaces = cls.namespaces()
        for ns in namespaces:
            if ns["email_address"] == email_address:
                return (cls(ns["id"]), ns)
        return (None, None)

    def __init__(self, namespace, apiBase="http://localhost:5555/n/"):
        self.namespace = namespace
        self.apiBase = apiBase

    def _get_resources(self, resource, cls, **kwargs):
        url = "%s%s/%s?" % (self.apiBase, self.namespace, resource)
        for arg in kwargs:
            url += "%s=%s&" % (arg, kwargs[arg])
        response = requests.get(url)
        if response.status_code != 200:
            response.raise_for_status()

        result = response.json()
        ret = []
        for entry in result:
            ret.append(cls.from_dict(entry))
        return ret

    def _get_resource(self, resource, cls, resource_id, **kwargs):
        """Get an individual REST resource"""
        url = "%s%s/%s/%s?" % (self.apiBase, self.namespace, resource,
                               resource_id)
        for arg in kwargs:
            url += "%s=%s&" % (arg, kwargs[arg])
        url = url[:-1]
        response = requests.get(url)
        if response.status_code != 200:
            response.raise_for_status()

        result = response.json()
        return cls.from_dict(result)

    def _create_resource(self, resource, cls, contents):
        url = "%s%s/%s" % (self.apiBase, self.namespace, resource)
        response = requests.post(url, data=json.dumps(contents))
        result = response.json()
        return cls.from_dict(result)

    def _create_resources(self, resource, cls, contents):
        """batch resource creation and parse the returned list"""
        url = "%s%s/%s" % (self.apiBase, self.namespace, resource)
        response = requests.post(url, data=json.dumps(contents))
        result = response.json()
        ret = []

        for entry in result:
            ret.append(cls.from_dict(entry))
        return ret

    def _update_resource(self, resource, cls, id, data):
        url = "%s%s/%s" % (self.apiBase, self.namespace, resource)
        response = requests.post(url, data=json.dumps(data))
        if response.status_code != 200:
            response.raise_for_status()

        result = response.json()
        return cls.from_dict(result)

    def get_namespaces(self, **kwargs):
        return self._get_resources("namespaces", Namespace, **kwargs)

    def get_messages(self, **kwargs):
        return self._get_resources("messages", Message, **kwargs)

    def get_threads(self, **kwargs):
        return self._get_resources("threads", Thread, **kwargs)

    def get_thread(self, id, **kwargs):
        return self._get_resource("threads", Thread, id, **kwargs)

    def get_drafts(self, **kwargs):
        return self._get_resources("drafts", Draft, **kwargs)

    def get_draft(self, id, **kwargs):
        return self._get_resource("drafts", Draft, id, **kwargs)

    def get_events(self, **kwargs):
        return self._get_resources("events", Event, **kwargs)

    def get_event(self, id, **kwargs):
        return self._get_resource("events", Event, id, **kwargs)

    def get_files(self, **kwargs):
        return self._get_resources("files", File, **kwargs)

    def get_file(self, id, **kwargs):
        return self._get_resource("files", File, id, **kwargs)

    def create_draft(self, body):
        return self._create_resource("drafts", Draft, body)

    def create_tag(self, tagname):
        return self._create_resource("tags", Tag, {"name": tagname})

    def create_files(self, body):
        url = "%s%s/files" % (self.apiBase, self.namespace)
        response = requests.post(url, files=body)
        result = response.json()
        ret = []
        for entry in result:
            ret.append(File.from_dict(entry))
        return ret

    def update_tags(self, thread_id, tags):
        url = "%s%s/threads/%s" % (self.apiBase, self.namespace, thread_id)
        return requests.put(url, data=json.dumps(tags))

    def send_message(self, message):
        url = "%s%s/send" % (self.apiBase, self.namespace)
        send_req = requests.post(url, data=json.dumps(message))
        return send_req

    def send_draft(self, draft_id, version):
        return self._update_resource("send", Draft, id,
                                     {"draft_id": draft_id,
                                      "version": version})
