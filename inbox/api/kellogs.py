import datetime
import calendar
from json import JSONEncoder, dumps

from flask import Response

from inbox.models import (Message, Part, Contact, Calendar, Event,
                          Participant, Time, TimeSpan, Date, DateSpan,
                          Thread, Namespace, Block, Webhook, Lens, Tag)


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
            'object': 'namespace',
            'namespace_id': obj.public_id,

            # Account specific
            'account_id': obj.account.public_id,
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
            'namespace_id': _get_namespace_public_id(obj),
            'subject': obj.subject,
            'from': format_address_list(obj.from_addr),
            'to': format_address_list(obj.to_addr),
            'cc': format_address_list(obj.cc_addr),
            'bcc': format_address_list(obj.bcc_addr),
            'date': obj.received_date,
            'thread_id': obj.thread.public_id,
            'snippet': obj.snippet,
            'body': obj.sanitized_body,
            'unread': not obj.is_read,
            'files': [{
                'content_type': b.content_type,
                'size': b.size,
                'filename': b.filename,
                'id': b.public_id} for b in [p.block for p in obj.parts
                                             if p.is_attachment]]
        }
        # If the message is a draft (Inbox-created or otherwise):
        if obj.is_draft:
            resp['object'] = 'draft'
            resp['version'] = obj.version
        if obj.state:
            resp['state'] = obj.state
        return resp

    elif isinstance(obj, Thread):
        return {
            'id': obj.public_id,
            'object': 'thread',
            'namespace_id': _get_namespace_public_id(obj),
            'subject': obj.subject,
            'participants': format_address_list(obj.participants),
            'last_message_timestamp': obj.recentdate,
            'first_message_timestamp': obj.subjectdate,
            'snippet': obj.snippet,
            'message_ids': [m.public_id for m in obj.messages if not
                            m.is_draft],
            'draft_ids': [m.public_id for m in obj.drafts],
            'tags': [{'name': tag.name, 'id': tag.public_id}
                     for tag in obj.tags]
        }

    elif isinstance(obj, Contact):
        return {
            'id': obj.public_id,
            'object': 'contact',
            'namespace_id': _get_namespace_public_id(obj),
            'name': obj.name,
            'email': obj.email_address
        }

    elif isinstance(obj, Event):
        return {
            'id': obj.public_id,
            'object': 'event',
            'namespace_id': _get_namespace_public_id(obj),
            'calendar_id': obj.calendar.public_id if obj.calendar else None,
            'title': obj.title,
            'description': obj.description,
            'participants': [encode(p) for p in obj.participants],
            'read_only': obj.read_only,
            'location': obj.location,
            'when': encode(obj.when)
        }

    elif isinstance(obj, Calendar):
        return {
            'id': obj.public_id,
            'object': 'calendar',
            'namespace': _get_namespace_public_id(obj),
            'name': obj.name,
            'description': obj.description,
            'read_only': obj.read_only,
            'event_ids': [e.public_id for e in obj.events],
        }

    elif isinstance(obj, Participant):
        return {
            'id': obj.public_id,
            'name': obj.name,
            'email': obj.email_address,
            'status': obj.status,
        }

    elif isinstance(obj, Time):
        return {
            'object': 'time',
            'time': obj.time
        }

    elif isinstance(obj, TimeSpan):
        return {
            'object': 'timespan',
            'start_time': obj.start_time,
            'end_time': obj.end_time
        }

    elif isinstance(obj, Date):
        return {
            'object': 'date',
            'date': obj.date.isoformat()
        }

    elif isinstance(obj, DateSpan):
        return {
            'object': 'datespan',
            'start_date': obj.start_date.isoformat(),
            'end_date': obj.end_date.isoformat()
        }

    elif isinstance(obj, Block):  # ie: Attachments/Files
        resp = {
            'id': obj.public_id,
            'object': 'file',
            'namespace_id': _get_namespace_public_id(obj),
            'content_type': obj.content_type,
            'size': obj.size,
            'filename': obj.filename,
            'is_embedded': False,
            'message_id': None
        }
        if isinstance(obj, Part):
            # if obj is actually a message attachment (and not merely an
            # uploaded file), set additional properties
            resp.update({
                'is_embedded': obj.is_embedded,
                'message_id': obj.message.public_id,
            })
        return resp

    elif isinstance(obj, Webhook):
        resp = encode(obj.lens, namespace_public_id)
        # resp is deliberately created in this order so that the 'id'
        # and 'object' values of the webhook and not the lens are
        # returned.
        resp.update({
            'id': obj.public_id,
            'object': 'webhook',
            'namespace_id': _get_namespace_public_id(obj),
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
            'namespace_id': _get_namespace_public_id(obj),
            'to': obj.to_addr,
            'from': obj.from_addr,
            'cc': obj.cc_addr,
            'bcc': obj.bcc_addr,
            'any_email': obj.any_email,
            'subject': obj.subject,
            'thread_id': obj.thread_public_id,
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
            'namespace_id': _get_namespace_public_id(obj)
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
