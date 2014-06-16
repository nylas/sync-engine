import datetime
import calendar
from json import JSONEncoder, dumps

from flask import Response

from inbox.models import (
    Message, Account, Part, Contact, Thread, Namespace, Block, Webhook, Lens,
    Tag, SpoolMessage)


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
                'namespace': obj.namespace.public_id,
                'subject': obj.subject,
                'from': format_address_list(obj.from_addr),
                'to': format_address_list(obj.to_addr),
                'cc': format_address_list(obj.cc_addr),
                'bcc': format_address_list(obj.bcc_addr),
                'date': obj.received_date,
                'thread': obj.thread.public_id,
                'files': [p.public_id for p in obj.parts if p.is_attachment],
                'body': obj.sanitized_body,
                'unread': not obj.is_read,
            }

            if isinstance(obj, SpoolMessage):
                resp['state'] = obj.state
                if obj.state != 'sent':
                    # Don't expose thread id on drafts for now.
                    del resp['thread']
                    resp['object'] = 'draft'

            return resp

        elif isinstance(obj, Thread):
            return {
                'id': obj.public_id,
                'object': 'thread',
                'namespace': obj.namespace.public_id,
                'subject': obj.subject,
                'participants': format_address_list(obj.participants),
                'last_message_timestamp': obj.recentdate,
                'subject_date': obj.subjectdate,
                'snippet': obj.snippet,
                'messages':  [m.public_id for m in obj.messages],  # for now
                'tags': [self.default(tag) for tag in obj.tags]
            }

        elif isinstance(obj, Contact):
            return {
                'id': obj.public_id,
                'object': 'contact',
                'namespace': obj.namespace.public_id,
                'name': obj.name,
                'email': obj.email_address
            }

        elif isinstance(obj, Part):  # ie: Attachments
            return {
                'id': obj.public_id,
                'object': 'file',
                'namespace': obj.namespace.public_id,
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
                'namespace': obj.namespace.public_id,
                'content_type': obj.content_type,
                'size': obj.size,
            }

        elif isinstance(obj, Webhook):
            resp = self.default(obj.lens)
            # resp is deliberately created in this order so that the 'id' and
            # 'object' values of the webhook and not the lens are returned.
            resp.update({
                'id': obj.public_id,
                'object': 'webhook',
                'namespace': obj.namespace.public_id,

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
                'namespace': obj.namespace.public_id,

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
            }

        elif isinstance(obj, Account):
            # Shouldn't ever need to serialize these...
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
