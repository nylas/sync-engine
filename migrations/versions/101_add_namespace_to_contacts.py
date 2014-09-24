"""add_namespace_to_contacts

Revision ID: 3bb01fcc755e
Revises:5a68ac0e3e9
Create Date: 2014-09-22 02:33:53.301883

"""

# revision identifiers, used by Alembic.
revision = '3bb01fcc755e'
down_revision = '5a68ac0e3e9'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.add_column('contact', sa.Column('namespace_id', sa.Integer(),
                                       sa.ForeignKey('namespace.id')))

    conn = op.get_bind()
    conn.execute(text('''
        UPDATE contact JOIN namespace ON contact.account_id=namespace.account_id
        SET contact.namespace_id=namespace.id'''))

    op.drop_constraint(u'uid', 'contact', type_='unique')
    op.drop_constraint('contact_ibfk_1', 'contact', type_='foreignkey')
    op.create_unique_constraint('uid', 'contact', ['uid', 'source',
                                                   'namespace_id',
                                                   'provider_name'])
    op.drop_column('contact', 'account_id')


def downgrade():
    raise Exception()
