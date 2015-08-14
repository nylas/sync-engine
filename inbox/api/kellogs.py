import arrow
import datetime
import calendar
from json import JSONEncoder, dumps
from flask import Response

from inbox.models import (Message, Contact, Calendar, Event, When,
                          Thread, Namespace, Block, Category, Account)
from inbox.models.event import RecurringEvent, RecurringEventOverride
from nylas.logging import get_logger
log = get_logger()


def format_address_list(addresses):
    if addresses is None:
        return []
    return [{'name': name, 'email': email} for name, email in addresses]


def format_categories(categories):
    if categories is None:
        return []
    return [{'id': category.public_id, 'name': category.name,
             'display_name': category.api_display_name} for category in
             categories]


def encode(obj, namespace_public_id=None, expand=False, legacy_nsid=False):
    try:
        return _encode(obj, namespace_public_id, expand,
                       legacy_nsid=legacy_nsid)
    except Exception as e:
        error_context = {
            "id": getattr(obj, "id", None),
            "cls": str(getattr(obj, "__class__", None)),
            "exception": e
        }
        log.error("object encoding failure", **error_context)
        raise


def _encode(obj, namespace_public_id=None, expand=False, legacy_nsid=False):
    """
    Returns a dictionary representation of an Inbox model object obj, or
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

    def _format_participant_data(participant):
        """Event.participants is a JSON blob which may contain internal data.
        This function returns a dict with only the data we want to make
        public."""
        dct = {}
        for attribute in ['name', 'status', 'email', 'comment']:
            dct[attribute] = participant.get(attribute)

        return dct

    def _get_lowercase_class_name(obj):
        return type(obj).__name__.lower()

    if legacy_nsid:
        public_id_key_name = 'namespace_id'
    else:
        public_id_key_name = 'account_id'

    # Flask's jsonify() doesn't handle datetimes or json arrays as primary
    # objects.
    if isinstance(obj, datetime.datetime):
        return calendar.timegm(obj.utctimetuple())

    if isinstance(obj, datetime.date):
        return obj.isoformat()

    if isinstance(obj, arrow.arrow.Arrow):
        return encode(obj.datetime, legacy_nsid=legacy_nsid)

    # TODO deprecate this and remove -- legacy_nsid
    elif isinstance(obj, Namespace) and legacy_nsid:
        return {
            'id': obj.public_id,
            'object': 'namespace',
            'namespace_id': obj.public_id,

            # Account specific
            'account_id': obj.account.public_id,
            'email_address': obj.account.email_address,
            'name': obj.account.name,
            'provider': obj.account.provider,
            'organization_unit': obj.account.category_type
        }
    elif isinstance(obj, Namespace):  # these are now "Account" objects
        return {
            'id': obj.public_id,
            'object': 'account',
            'account_id': obj.public_id,

            'email_address': obj.account.email_address,
            'name': obj.account.name,
            'provider': obj.account.provider,
            'organization_unit': obj.account.category_type
        }

    elif isinstance(obj, Account) and not legacy_nsid:
        raise Exception("Should never be serializing accounts (legacy_nsid)")

    elif isinstance(obj, Account):
        return {
            'account_id': obj.namespace.public_id,  # ugh
            'id': obj.namespace.public_id,  # ugh
            'object': 'account',
            'email_address': obj.email_address,
            'name': obj.name,
            'organization_unit': obj.category_type,

            'provider': obj.provider,

            # TODO add capabilities/scope (i.e. mail, contacts, cal, etc.)

            # 'status':  'syncing',  # TODO what are values here
            # 'last_sync':  1398790077,  # tuesday 4/29
        }

    elif isinstance(obj, Message):
        resp = {
            'id': obj.public_id,
            'object': 'message',
            public_id_key_name: _get_namespace_public_id(obj),
            'subject': obj.subject,
            'from': format_address_list(obj.from_addr),
            'reply_to': format_address_list(obj.reply_to),
            'to': format_address_list(obj.to_addr),
            'cc': format_address_list(obj.cc_addr),
            'bcc': format_address_list(obj.bcc_addr),
            'date': obj.received_date,
            'thread_id': obj.thread.public_id,
            'snippet': obj.snippet,
            'body': obj.body,
            'unread': not obj.is_read,
            'starred': obj.is_starred,
            'files': obj.api_attachment_metadata,
            'events': [encode(e, legacy_nsid=legacy_nsid) for e in obj.events]
        }

        categories = format_categories(obj.categories)
        if obj.namespace.account.category_type == 'folder':
            resp['folder'] = categories[0] if categories else None
        else:
            resp['labels'] = categories

        # If the message is a draft (Inbox-created or otherwise):
        if obj.is_draft:
            resp['object'] = 'draft'
            resp['version'] = obj.version
            if obj.reply_to_message is not None:
                resp['reply_to_message_id'] = obj.reply_to_message.public_id
            else:
                resp['reply_to_message_id'] = None

        if expand:
            resp['headers'] = {
                'Message-Id': obj.message_id_header,
                'In-Reply-To': obj.in_reply_to,
                'References': obj.references
            }

        return resp

    elif isinstance(obj, Thread):
        base = {
            'id': obj.public_id,
            'object': 'thread',
            public_id_key_name: _get_namespace_public_id(obj),
            'subject': obj.subject,
            'participants': format_address_list(obj.participants),
            'last_message_timestamp': obj.recentdate,
            'last_message_received_timestamp': obj.receivedrecentdate,
            'first_message_timestamp': obj.subjectdate,
            'snippet': obj.snippet,
            'unread': obj.unread,
            'starred': obj.starred,
            'has_attachments': obj.has_attachments,
            'version': obj.version,
            # For backwards-compatibility -- remove after deprecating tags API
            'tags': obj.tags
        }

        categories = format_categories(obj.categories)
        if obj.namespace.account.category_type == 'folder':
            base['folders'] = categories
        else:
            base['labels'] = categories

        if not expand:
            base['message_ids'] = \
                [m.public_id for m in obj.messages if not m.is_draft]
            base['draft_ids'] = [m.public_id for m in obj.drafts]
            return base

        # Expand messages within threads
        all_expanded_messages = []
        all_expanded_drafts = []
        for msg in obj.messages:
            resp = {
                'id': msg.public_id,
                'object': 'message',
                public_id_key_name: _get_namespace_public_id(msg),
                'subject': msg.subject,
                'from': format_address_list(msg.from_addr),
                'reply_to': format_address_list(msg.reply_to),
                'to': format_address_list(msg.to_addr),
                'cc': format_address_list(msg.cc_addr),
                'bcc': format_address_list(msg.bcc_addr),
                'date': msg.received_date,
                'thread_id': obj.public_id,
                'snippet': msg.snippet,
                'unread': not msg.is_read,
                'starred': msg.is_starred,
                'files': msg.api_attachment_metadata
            }
            categories = format_categories(msg.categories)
            if obj.namespace.account.category_type == 'folder':
                resp['folder'] = categories[0] if categories else None
            else:
                resp['labels'] = categories

            if msg.is_draft:
                resp['object'] = 'draft'
                resp['version'] = msg.version
                if msg.reply_to_message is not None:
                    resp['reply_to_message_id'] = \
                        msg.reply_to_message.public_id
                else:
                    resp['reply_to_message_id'] = None
                all_expanded_drafts.append(resp)
            else:
                all_expanded_messages.append(resp)

        base['messages'] = all_expanded_messages
        base['drafts'] = all_expanded_drafts
        return base

    elif isinstance(obj, Contact):
        return {
            'id': obj.public_id,
            'object': 'contact',
            public_id_key_name: _get_namespace_public_id(obj),
            'name': obj.name,
            'email': obj.email_address
        }

    elif isinstance(obj, Event):
        resp = {
            'id': obj.public_id,
            'object': 'event',
            public_id_key_name: _get_namespace_public_id(obj),
            'calendar_id': obj.calendar.public_id if obj.calendar else None,
            'message_id': obj.message.public_id if obj.message else None,
            'title': obj.title,
            'description': obj.description,
            'owner': obj.owner,
            'participants': [_format_participant_data(participant)
                             for participant in obj.participants],
            'read_only': obj.read_only,
            'location': obj.location,
            'when': encode(obj.when, legacy_nsid=legacy_nsid),
            'busy': obj.busy,
            'status': obj.status,
        }
        if isinstance(obj, RecurringEvent):
            resp['recurrence'] = {
                'rrule': obj.recurring,
                'timezone': obj.start_timezone
            }
        if isinstance(obj, RecurringEventOverride):
            resp['original_start_time'] = encode(obj.original_start_time,
                                                 legacy_nsid=legacy_nsid)
            if obj.master:
                resp['master_event_id'] = obj.master.public_id
        return resp

    elif isinstance(obj, Calendar):
        return {
            'id': obj.public_id,
            'object': 'calendar',
            public_id_key_name: _get_namespace_public_id(obj),
            'name': obj.name,
            'description': obj.description,
            'read_only': obj.read_only,
        }

    elif isinstance(obj, When):
        # Get time dictionary e.g. 'start_time': x, 'end_time': y or 'date': z
        times = obj.get_time_dict()
        resp = {k: encode(v, legacy_nsid=legacy_nsid) for
                                         k, v in times.iteritems()}
        resp['object'] = _get_lowercase_class_name(obj)
        return resp

    elif isinstance(obj, Block):  # ie: Attachments/Files
        resp = {
            'id': obj.public_id,
            'object': 'file',
            public_id_key_name: _get_namespace_public_id(obj),
            'content_type': obj.content_type,
            'size': obj.size,
            'filename': obj.filename,
        }
        if len(obj.parts):
            # if obj is actually a message attachment (and not merely an
            # uploaded file), set additional properties
            resp.update({
                'message_ids': [p.message.public_id for p in obj.parts]
            })

        return resp

    elif isinstance(obj, Category):
        # 'object' is set to 'folder' or 'label'
        resp = {
            'id': obj.public_id,
            'object': obj.type,
            public_id_key_name: _get_namespace_public_id(obj),
            'name': obj.name,
            'display_name': obj.api_display_name
        }
        return resp


class APIEncoder(object):
    """
    Provides methods for serializing Inbox objects. If the optional
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
    def __init__(self, namespace_public_id=None, expand=False,
                 legacy_nsid=False):
        self.encoder_class = self._encoder_factory(namespace_public_id, expand,
                                                   legacy_nsid)

    def _encoder_factory(self, namespace_public_id, expand, legacy_nsid):
        class InternalEncoder(JSONEncoder):
            def default(self, obj):
                custom_representation = encode(obj,
                                               namespace_public_id,
                                               expand=expand,
                                               legacy_nsid=legacy_nsid)
                if custom_representation is not None:
                    return custom_representation
                # Let the base class default method raise the TypeError
                return JSONEncoder.default(self, obj)
        return InternalEncoder

    def cereal(self, obj, pretty=False):
        """
        Returns the JSON string representation of obj.

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
        """
        Returns a Flask Response object encapsulating the JSON
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
