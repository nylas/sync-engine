""" Remove duplicated Gmail Message objects and tighten constraints for Gmail messages.

Revision ID: 4b4c5579c083
Revises: 1925c535a52d
Create Date: 2014-07-17 00:01:09.410292

"""

# revision identifiers, used by Alembic.
revision = '4b4c5579c083'
down_revision = '4b4674f1a726'

from alembic import op
from sqlalchemy import func


def upgrade():
    op.drop_constraint('messagecontactassociation_ibfk_1',
                       'messagecontactassociation', type_='foreignkey')
    op.drop_constraint('messagecontactassociation_ibfk_2',
                       'messagecontactassociation', type_='foreignkey')
    op.create_foreign_key('messagecontactassociation_ibfk_1',
                          'messagecontactassociation', 'contact',
                          ['contact_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('messagecontactassociation_ibfk_2',
                          'messagecontactassociation', 'message',
                          ['message_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('imapuid_ibfk_2', 'imapuid', type_='foreignkey')
    op.create_foreign_key('imapuid_ibfk_2', 'imapuid', 'message',
                          ['message_id'], ['id'], ondelete='CASCADE')
    from inbox.models import Message
    from inbox.models.session import session_scope

    with session_scope(versioned=False) \
            as db_session:
        groups = db_session.query(
            Message.id, Message.thread_id, Message.g_msgid)\
            .filter(~Message.g_msgid.is_(None))\
            .group_by(Message.thread_id, Message.g_msgid).having(
                func.count(Message.id) > 1).all()

        for message_id, thread_id, g_msgid in groups:
            print "deleting duplicates of ({}, {}), saving {}".format(
                thread_id, g_msgid, message_id)
            db_session.query(Message).filter(
                Message.thread_id == thread_id,
                Message.g_msgid == g_msgid,
                Message.id != message_id).delete()

    op.execute('ALTER TABLE message ADD UNIQUE INDEX ix_message_thread_id_g_msgid (thread_id, g_msgid)')


def downgrade():
    pass
