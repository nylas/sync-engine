from inbox.server.config import load_config
load_config()
from inbox.server.models import session_scope
from inbox.server.contacts.process_mail import update_contacts_from_message
from inbox.server.models.tables.base import (Message, SearchSignal,
                                             register_backends)
register_backends()


def main():
    with session_scope() as db_session:
        # Delete existing signals.
        signals = db_session.query(SearchSignal).all()
        for signal in signals:
            db_session.delete(signal)
        db_session.commit()
        messages = db_session.query(Message).all()
        for message in messages:
            account_id = message.namespace.account_id
            update_contacts_from_message(account_id, message)

        db_session.commit()


main()
