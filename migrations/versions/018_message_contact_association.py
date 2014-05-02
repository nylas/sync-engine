"""message contact association

Revision ID: 223041bb858b
Revises: 2c9f3a06de09
Create Date: 2014-04-28 23:52:05.449401

"""

# revision identifiers, used by Alembic.
revision = '223041bb858b'
down_revision = '2c9f3a06de09'


from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'messagecontactassociation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('field',
                  sa.Enum('from_addr', 'to_addr', 'cc_addr', 'bcc_addr'),
                  nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ),
        sa.ForeignKeyConstraint(['message_id'], ['message.id'], ),
        sa.PrimaryKeyConstraint('id', 'contact_id', 'message_id')
    )

    # Yes, this is a terrible hack. But tools/rerank_contacts.py already
    # contains a script to process contacts from messages, so it's very
    # expedient.
    import sys
    sys.path.append('./tools')
    from rerank_contacts import rerank_contacts
    rerank_contacts()


def downgrade():
    op.drop_table('messagecontactassociation')
