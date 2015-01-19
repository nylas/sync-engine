from inbox.models.message import Message


def reconcile_message(new_message, session):
    """
    Check to see if the (synced) Message instance new_message was originally
    created and sent via the Inbox API (based on the X-Inbox-Uid header. If so,
    update the existing message with new attributes from the synced message
    and return it.

    """
    if new_message.inbox_uid is not None:
        existing_message = session.query(Message).filter(
            Message.namespace_id == new_message.namespace_id,
            Message.inbox_uid == new_message.inbox_uid,
            Message.is_created == True).first()

        if existing_message is None:
            return None

        existing_message.message_id_header = new_message.message_id_header
        existing_message.full_body = new_message.full_body
        existing_message.sanitized_body = new_message.sanitized_body
        existing_message.snippet = new_message.snippet
        existing_message.references = new_message.references

        return existing_message


def transaction_objects():
    """
    Return the mapping from model name to API object name - which becomes the
    Transaction.object_type - for models that generate Transactions (i.e.
    models that implement the HasRevisions mixin).

    """
    from inbox.models.mixins import HasRevisions

    return dict((m.__tablename__, m.API_OBJECT_NAME) for
                m in HasRevisions.__subclasses__())
