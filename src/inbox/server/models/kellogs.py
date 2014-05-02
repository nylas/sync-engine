import datetime
import calendar
from json import JSONEncoder, dumps

from flask import Response

from inbox.server.models.tables.base import (
    Message, SharedFolder, User, Account, Part,
    Contact, Thread, Namespace, Block)


def format_address_list(addresses):
    return [{'name': name, 'email': email} for name, email in addresses]


# Flask's jsonify() doesn't handle datetimes or
# json arrays as primary objects
class APIEncoder(JSONEncoder):

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return calendar.timegm(obj.utctimetuple())

        elif isinstance(obj, Namespace):
            return {
                'id':  obj.public_id,
                'object': 'namepace',
                'ns':  obj.public_id,

                # Account specific
                'account':  obj.account.public_id,
                'email_address':  obj.account.email_address,
                'provider':  obj.account.provider,
                # 'status':  'syncing',  # TODO what are values here
                # 'last_sync':  1398790077,  # tuesday 4/29
                # 'scope': ['mail', 'contacts']
            }

        elif isinstance(obj, Message):
            resp = {
                'id':  obj.public_id,
                'object': 'message',
                'ns': obj.namespace.public_id,
                'subject': obj.subject,
                'from': format_address_list(obj.from_addr),
                'to': format_address_list(obj.to_addr),
                'cc': format_address_list(obj.cc_addr),
                'bcc': format_address_list(obj.bcc_addr),
                'date': obj.received_date,
                'thread': obj.thread.public_id,
                'size': obj.size,
                'files': [],  # TODO calculate attachments from blocks
                'body': obj.sanitized_body,
                # 'snippet'     : obj.snippet,
                # 'list_info'   : obj.mailing_list_headers
            }
            if obj.is_draft:
                resp['is_draft'] = obj.is_draft
            return resp

        elif isinstance(obj, Thread):
            return {
                'id':  obj.public_id,
                'object':  'thread',
                'ns':  obj.namespace.public_id,
                'subject':  obj.subject,
                'participants':  obj.participants,
                'recent_date':  obj.recentdate,
                'subject_date': obj.subjectdate,
                'messages':  [m.public_id for m in obj.messages]  # for now
            }

        elif isinstance(obj, Contact):
            return {
                'id': obj.public_id,
                'object': 'contact',
                'ns': obj.namespace.public_id,
                'name': obj.name,
                'email_address': obj.email_address
            }

        elif isinstance(obj, Part):  # ie: Attachments
            return {
                'id': obj.public_id,
                'object': 'file',
                'ns': obj.namespace.public_id,
                'content_type': obj.content_type,
                'size': obj.size,
                'filename': obj.filename or obj.content_id,
                'is_inline': obj.content_disposition is not None
                and obj.content_disposition.lower() == 'inline',
                'message': obj.message.public_id
            }

        elif isinstance(obj, Block):  # ie: Files
            # TODO consider adding more info?
            return {
                'id': obj.public_id,
                'object': 'file',
                'ns': obj.namespace.public_id,
                'content_type': obj.content_type,
                'size': obj.size,
            }

        elif isinstance(obj, User):
            return {
                'id': obj.public_id,
                'object': 'user',
                'name': obj.name,
                'namespaces': [a.namespace.public_id for a in obj.accounts]
                # TOD
            }
            raise NotImplementedError

        elif isinstance(obj, Account):
            # Shouldn't ever need to serialize these...
            raise NotImplementedError

        elif isinstance(obj, SharedFolder):
            raise NotImplementedError

        # elif isinstance(obj, Webhook):
        #     pass

        # elif insstance(obj, CalendarEvent):
        #     pass

        # Let the base class default method raise the TypeError
        return JSONEncoder.default(self, obj)


def cereal(obj, pretty=False):
    if pretty:
        return dumps(obj,
                     sort_keys=True,
                     indent=4,
                     separators=(',', ': '),
                     cls=APIEncoder)
    return dumps(obj, cls=APIEncoder)


def jsonify(obj):
    return Response(cereal(obj, pretty=True),
                    mimetype='application/json')
