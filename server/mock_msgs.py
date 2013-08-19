
from models import MessageMeta

m = MessageMeta()

m.date = "Some dummy date"

m.subject = u"Lorem Ipsum Subject"

m.from_addr = [[u"Firstname", u"lastname", u"emailaddr", u"domain.com"]]
m.sender = [[u"Firstname", u"lastname", u"emailaddr", u"domain.com"]]
m.reply_to = [[u"Firstname", u"lastname", u"emailaddr", u"domain.com"]]
m.to_addr = [[u"Firstname", u"lastname", u"emailaddr", u"domain.com"]]
m.cc_addr = [[u"Firstname", u"lastname", u"emailaddr", u"domain.com"]]
m.bcc_addr = [[u"Firstname", u"lastname", u"emailaddr", u"domain.com"]]
m.in_reply_to = [[u"Firstname", u"lastname", u"emailaddr", u"domain.com"]]

m.message_id = u"Blahbhalhblahihwohifsadlfajsdf"

m.internaldate = message_dict['INTERNALDATE']
m.g_thrid = str(message_dict['X-GM-THRID'])
m.g_msgid = str(message_dict['X-GM-MSGID'])
m.g_labels = str(message_dict['X-GM-LABELS'])

m.in_inbox = bool('\Inbox' in m.g_labels)
if m.in_inbox:
    print 'Message is in the inbox!'

m.flags = message_dict['FLAGS']

m.g_user_id = self.user_obj.g_user_id