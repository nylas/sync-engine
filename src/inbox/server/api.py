import uuid

import zerorpc

from inbox.server.config import config
from inbox.server.contacts import search_util
from inbox.server.models import session_scope
from inbox.server.models.kellogs import cereal
from inbox.server.mailsync.backends.imap.account import (total_stored_data,
                                                         total_stored_messages)
from inbox.server.models.tables.base import (Message, Contact, Thread)
from inbox.server.models.namespace import threads_for_folder
from inbox.server.sendmail.base import (send, reply, recipients,
                                        create_attachment_metadata)
from inbox.server.log import get_logger
log = get_logger(purpose='api')

# Provider name for contacts added via this API
INBOX_PROVIDER_NAME = 'inbox'


class NSAuthError(Exception):
    pass


class API(object):
    _zmq_search = None
    _sync = None

    # Remember, ZeroRPC doesn't support keyword arguments in exposed methods

    @property
    def z_search(self):
        """ Proxy function for the ZeroMQ search service. """
        if not self._zmq_search:
            search_srv_loc = config.get('SEARCH_SERVER_LOC', None)
            assert search_srv_loc, "Where is the Search ZMQ service?"
            self._zmq_search = zerorpc.Client(search_srv_loc)
        return self._zmq_search.search

    def send_new(self, to, subject, body, attachments=None, cc=None, bcc=None):
        """
        Send an email from the authorized user account for this namespace.

        Parameters
        ----------
        to : list
            a list of utf-8 encoded strings
        subject : string
            a utf-8 encoded string
        body : string
            a utf-8 encoded string
        attachments: list, optional
            a list of filenames to attach
        cc : list, optional
            a list of utf-8 encoded strings
        bcc : list, optional
            a list of utf-8 encoded strings

        """
        account = self.namespace.account
        assert account is not None, "Can't send mail with this namespace"

        attachfiles = create_attachment_metadata(attachments) if attachments\
            else attachments

        send(account, recipients(to, cc, bcc), subject, body, attachfiles)

        return 'OK'

    def send_reply(self, namespace_id, thread_id, to, subject, body,
                   attachments=None, cc=None, bcc=None):
        """
        Send an email reply from the authorized user account for this
        namespace.

        Parameters
        ----------
        thread_id : int
        to : list
            a list of utf-8 encoded strings
        subject : string
            a utf-8 encoded string
        body : string
            a utf-8 encoded string
        attachments: list, optional
            a list of filenames to attach
        cc : list, optional
            a list of utf-8 encoded strings
        bcc : list, optional
            a list of utf-8 encoded strings

        """
        account = self.namespace.account
        assert account is not None, "Can't send mail with this namespace"

        attachfiles = create_attachment_metadata(attachments) if attachments\
            else attachments

        reply(account, thread_id, recipients(to, cc, bcc), subject, body,
              attachfiles)

        return 'OK'

    def search_folder(self, search_query):
        log.info("Searching with query: {0}".format(search_query))
        results = self.z_search(self.namespace.id, search_query)
        message_ids = [r[0] for r in results]
        log.info("Found {0} messages".format(len(message_ids)))
        return message_ids

    def threads_for_folder(self, folder_name):
        """ Returns all threads in a given folder, together with associated
            messages. Supports shared folders and TODO namespaces as well, if
            caller auths with that namespace.

            Note that this may be more messages than included in the IMAP
            folder, since we fetch the full thread if one of the messages is in
            the requested folder.
        """
        with session_scope() as db_session:
            return [cereal(t) for t in threads_for_folder(
                self.namespace.id, db_session, folder_name)]

    def body_for_message(self, message_id):
        # TODO: Take namespace into account, currently doesn't matter since
        # one namespace only.
        with session_scope() as db_session:
            message = db_session.query(Message).join(Message.parts) \
                .filter(Message.id == message_id).one()
            return {'data': message.prettified_body}

    # Headers API:
    def headers_for_message(self, namespace_id, message_id):
        # TODO[kavya]: Take namespace into account, currently doesn't matter
        # since one namespace only.
        with session_scope() as db_session:
            message = db_session.query(Message).filter(
                Message.id == message_id).one()
            return message.headers

    # Mailing list API:
    def is_mailing_list_thread(self, namespace_id, thread_id):
        with session_scope() as db_session:
            thread = db_session.query(Thread).filter(
                Thread.id == thread_id,
                Thread.namespace_id == namespace_id).one()
            return thread.is_mailing_list_thread()

    def mailing_list_info_for_thread(self, namespace_id, thread_id):
        with session_scope() as db_session:
            thread = db_session.query(Thread).filter(
                Thread.id == thread_id,
                Thread.namespace_id == namespace_id).one()
            return thread.mailing_list_info

    # For first_10_subjects example:
    def first_n_subjects(self, n):
        with session_scope() as db_session:
            subjects = db_session.query(Thread.subject).filter(
                Thread.namespace_id == self.namespace.id).limit(n).all()
            return subjects

    def get_contact(self, contact_id):
        """Get all data for an existing contact."""
        with session_scope() as db_session:
            contact = db_session.query(Contact).filter_by(id=contact_id).one()
            return cereal(contact)

    def add_contact(self, account_id, contact_info):
        """Add a new contact to the specified IMAP account. Returns the ID of
        the added contact."""
        with session_scope() as db_session:
            contact = Contact(account_id=account_id, source='local',
                              provider_name=INBOX_PROVIDER_NAME,
                              uid=uuid.uuid4().hex)
            contact.name = contact_info['name']
            contact.email_address = contact_info['email']
            db_session.add(contact)
            db_session.commit()
            log.info("Added contact {0}".format(contact.id))
            return contact.id

    def update_contact(self, contact_id, contact_info):
        """Update data for an existing contact."""
        with session_scope() as db_session:
            contact = db_session.query(Contact).filter_by(id=contact_id).one()
            contact.name = contact_info['name']
            contact.email_address = contact_info['email']
            log.info("Updated contact {0}".format(contact.id))
            return 'OK'

    def search_contacts(self, account_id, query, max_results=10):
        """Search for contacts that match the given query."""
        with session_scope() as db_session:
            results = search_util.search(db_session, account_id, query,
                                         int(max_results))
            return [cereal(contact) for contact in results]
