import datetime
import calendar
from json import JSONEncoder, dumps

from flask import Response

from inbox.models import (Message, Part, Contact, Thread, Namespace, Block,
                          Webhook, Lens, Tag, SpoolMessage)


def format_address_list(addresses):
    if addresses is None:
        return []
    return [{'name': name, 'email': email} for name, email in addresses]


def encode(obj, namespace_public_id=None):
    """Returns a dictionary representation of an Inbox model object obj, or
    None if there is no such representation defined. If the optional
    namespace_public_id parameter is passed, it will used instead of fetching
    the namespace public id for each object. This improves performance when
    serializing large numbers of objects, but also means that you must take
    care to ONLY serialize objects that belong to the given namespace!

    Parameters
    ----------
    namespace_public_id: string, optional
        public id of the namespace to which the object to serialize belongs.

    Returns
    -------
    dictionary or None
    """
    def _get_namespace_public_id(obj):
        return namespace_public_id or obj.namespace.public_id

    # Flask's jsonify() doesn't handle datetimes or json arrays as primary
    # objects.
    if isinstance(obj, datetime.datetime):
        return calendar.timegm(obj.utctimetuple())

    elif isinstance(obj, Namespace):
        return {
            'id': obj.public_id,
            'object': 'namepace',
            'namespace': obj.public_id,

            # Account specific
            'account': obj.account.public_id,
            'email_address': obj.account.email_address,
            'provider': obj.account.provider,
            # 'status':  'syncing',  # TODO what are values here
            # 'last_sync':  1398790077,  # tuesday 4/29
            # 'scope': ['mail', 'contacts']
        }

    elif isinstance(obj, Message):
        resp = {
            'id': obj.public_id,
            'object': 'message',
            'namespace': _get_namespace_public_id(obj),
            'subject': obj.subject,
            'from': format_address_list(obj.from_addr),
            'to': format_address_list(obj.to_addr),
            'cc': format_address_list(obj.cc_addr),
            'bcc': format_address_list(obj.bcc_addr),
            'date': obj.received_date,
            'thread': obj.thread.public_id,
            'files': [p.public_id for p in obj.parts if
                      p.is_attachment],
            'body': obj.sanitized_body,
            'unread': not obj.is_read,
        }

        if isinstance(obj, SpoolMessage):
            resp['state'] = obj.state
            if obj.state != 'sent':
                resp['object'] = 'draft'

        return resp

    elif isinstance(obj, Thread):
        return {
            'id': obj.public_id,
            'object': 'thread',
            'namespace': _get_namespace_public_id(obj),
            'subject': obj.subject,
            'participants': format_address_list(obj.participants),
            'last_message_timestamp': obj.recentdate,
            'subject_date': obj.subjectdate,
            'snippet': obj.snippet,
            'messages':  [m.public_id for m in obj.messages if not
                          m.is_draft],
            'drafts': [m.public_id for m in obj.latest_drafts],
            'tags': [{'name': tag.name, 'id': tag.public_id}
                     for tag in obj.tags]
        }

    elif isinstance(obj, Contact):
        return {
            'id': obj.public_id,
            'object': 'contact',
            'namespace': _get_namespace_public_id(obj),
            'name': obj.name,
            'email': obj.email_address
        }

    elif isinstance(obj, Part):  # ie: Attachments
        return {
            'id': obj.public_id,
            'object': 'file',
            'namespace': _get_namespace_public_id(obj),
            'content_type': obj.content_type,
            'size': obj.size,
            'filename': obj.filename or obj.content_id,
            'is_embedded': obj.content_disposition is not None
            and obj.content_disposition.lower() == 'inline',
            'message': obj.message.public_id
        }

    elif isinstance(obj, Block):  # ie: Files
        # TODO consider adding more info?
        return {
            'id': obj.public_id,
            'object': 'file',
            'namespace': _get_namespace_public_id(obj),
            'content_type': obj.content_type,
            'size': obj.size,
        }

    elif isinstance(obj, Webhook):
        resp = encode(obj.lens, namespace_public_id)
        # resp is deliberately created in this order so that the 'id'
        # and 'object' values of the webhook and not the lens are
        # returned.
        resp.update({
            'id': obj.public_id,
            'object': 'webhook',
            'namespace': _get_namespace_public_id(obj),
            'callback_url': obj.callback_url,
            'failure_notify_url': obj.failure_notify_url,
            'include_body': obj.include_body,
            'active': obj.active,
        })
        return resp

    elif isinstance(obj, Lens):
        return {
            'id': obj.public_id,
            'object': 'lens',
            'namespace': _get_namespace_public_id(obj),
            'to': obj.to_addr,
            'from': obj.from_addr,
            'cc': obj.cc_addr,
            'bcc': obj.bcc_addr,
            'any_email': obj.any_email,
            'subject': obj.subject,
            'thread': obj.thread_public_id,
            'filename': obj.filename,
            'started_before': obj.started_before,
            'started_after': obj.started_after,
            'last_message_before': obj.last_message_before,
            'last_message_after': obj.last_message_after,
        }

    elif isinstance(obj, Tag):
        return {
            'id': obj.public_id,
            'object': 'tag',
            'name': obj.name,
            'namespace': _get_namespace_public_id(obj)
        }


class APIEncoder(object):
    """Provides methods for serializing Inbox objects. If the optional
    namespace_public_id parameter is passed, it will be bound and used instead
    of fetching the namespace public id for each object. This improves
    performance when serializing large numbers of objects, but also means that
    you must take care to ONLY serialize objects that belong to the given
    namespace!

    Parameters
    ----------
    namespace_public_id: string, optional
        public id of the namespace to which the object to serialize belongs.

    """
    def __init__(self, namespace_public_id=None):
        self.encoder_class = self._encoder_factory(namespace_public_id)

    def _encoder_factory(self, namespace_public_id):
        class InternalEncoder(JSONEncoder):
            def default(self, obj):
                custom_representation = encode(obj, namespace_public_id)
                if custom_representation is not None:
                    return custom_representation
                # Let the base class default method raise the TypeError
                return JSONEncoder.default(self, obj)
        return InternalEncoder

    def cereal(self, obj, pretty=False):
        """Returns the JSON string representation of obj.

        Parameters
        ----------
        obj: serializable object
        pretty: bool, optional
            Whether to pretty-print the string (with 4-space indentation).

        Raises
        ------
        TypeError
            If obj is not serializable.
        """
        if pretty:
            return dumps(obj,
                         sort_keys=True,
                         indent=4,
                         separators=(',', ': '),
                         cls=self.encoder_class)
        return dumps(obj, cls=self.encoder_class)

    def jsonify(self, obj):
        """Returns a Flask Response object encapsulating the JSON
        representation of obj.

        Parameters
        ----------
        obj: serializable object

        Raises
        ------
        TypeError
            If obj is not serializable.
        """
        return Response(self.cereal(obj, pretty=True),
                        mimetype='application/json')
