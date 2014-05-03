from datetime import datetime

from email.utils import parsedate_tz, mktime_tz
from flanker import mime
import json

from inbox.util.addr import parse_email_address_list


# Email from the sync dump exported to the 'test' db
with open('tests/data/messages/mailing_list_message.txt', 'r') as f:
    message = f.read()

# Repr for testing
parsed = mime.from_string(message)
headers = json.dumps(parsed.headers.items())
message_id = parsed.headers.get('Message-ID')

subject = parsed.headers.get('Subject').strip('Re: ')

sender = parsed.headers.get('Sender')
delivered_to = parsed.headers.get('Delivered-To')

_to = parsed.headers.get('To')
to_addr = parse_email_address_list(_to)[0][1]

_from = parsed.headers.get('From')
from_addr = parse_email_address_list(_from)[0][1]

date = parsed.headers.get('Date')
parsed_date = parsedate_tz(date)
timestamp = mktime_tz(parsed_date)
received_date = datetime.fromtimestamp(timestamp)

# We have to hard-code these values unfortunately
msg_id = 2
thread_id = 2
mailing_list_headers = {
    "List-Id": "<golang-nuts.googlegroups.com>",
    "List-Post": "<http://groups.google.com/group/golang-nuts/post>, <mailto:golang-nuts@googlegroups.com>",
    "List-Owner": None,
    "List-Subscribe": "<http://groups.google.com/group/golang-nuts/subscribe>, <mailto:golang-nuts+subscribe@googlegroups.com>",
    "List-Unsubscribe": "<http://groups.google.com/group/golang-nuts/subscribe>, <mailto:googlegroups-manage+332403668183+unsubscribe@googlegroups.com>",
    "List-Archive": "<http://groups.google.com/group/golang-nuts>",
    "List-Help": "<http://groups.google.com/support/>, <mailto:golang-nuts+help@googlegroups.com>"
    }

TEST_MSG = {
    'msg_id': msg_id,
    'thread_id': thread_id,
    'mailing_list_headers': mailing_list_headers,
    'all_headers': headers
}
