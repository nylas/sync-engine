"""generic_imap

Revision ID: 43cd2de5ad85
Revises: 2525c5245cc2
Create Date: 2014-08-01 14:36:09.980388

"""

# revision identifiers, used by Alembic.
revision = '43cd2de5ad85'
down_revision = '3bb5d61c895c'

from alembic import op
import sqlalchemy as sa
from inbox.models.session import session_scope
from sqlalchemy.ext.declarative import declarative_base
from inbox.ignition import main_engine
engine = main_engine()


def upgrade():
    op.create_table('genericaccount',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['id'], [u'imapaccount.id'],
                                            ondelete='CASCADE'),
                    sa.Column('password_id',
                              sa.Integer(), nullable=True),
                    sa.Column('provider',
                              sa.String(length=64), nullable=False),
                    sa.PrimaryKeyConstraint('id')
                    )

    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Account(Base):
        __table__ = Base.metadata.tables['account']

    class ImapAccount(Account):
        __table__ = Base.metadata.tables['imapaccount']

    class YahooAccount(ImapAccount):
        __table__ = Base.metadata.tables['yahooaccount']

    class AOLAccount(ImapAccount):
        __table__ = Base.metadata.tables['aolaccount']

    class GenericAccount(ImapAccount):
        __table__ = Base.metadata.tables['genericaccount']

    with session_scope(versioned=False, ignore_soft_deletes=False) \
            as db_session:
        for acct in db_session.query(YahooAccount):
            new_acct = GenericAccount(namespace=acct.namespace,
                                      provider='yahoo')
            new_acct.email_address = acct.email_address
            new_acct.password = acct.password
            db_session.add(new_acct)

        for acct in db_session.query(AOLAccount):
            new_acct = GenericAccount(namespace=acct.namespace,
                                      provider='aol')
            new_acct.email_address = acct.email_address
            new_acct.password = acct.password
            db_session.add(new_acct)

        db_session.commit()

    op.drop_table('aolaccount')
    op.drop_table('yahooaccount')
    op.drop_column('imapaccount', 'imap_host')


def downgrade():
    op.create_table('aolaccount',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['id'], [u'imapaccount.id'],
                                            ondelete='CASCADE'),
                    sa.Column('password', sa.String(256)),
                    sa.PrimaryKeyConstraint('id')
                    )

    op.create_table('yahooaccount',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['id'], [u'imapaccount.id'],
                                            ondelete='CASCADE'),
                    sa.Column('password', sa.String(256)),
                    sa.PrimaryKeyConstraint('id')
                    )

    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Account(Base):
        __table__ = Base.metadata.tables['account']

    class ImapAccount(Account):
        __table__ = Base.metadata.tables['imapaccount']

    class YahooAccount(ImapAccount):
        __table__ = Base.metadata.tables['yahooaccount']

    class AOLAccount(ImapAccount):
        __table__ = Base.metadata.tables['aolaccount']

    class GenericAccount(ImapAccount):
        __table__ = Base.metadata.tables['genericaccount']

    with session_scope(versioned=False, ignore_soft_deletes=False) \
            as db_session:
        for acct in db_session.query(GenericAccount):
            if acct.provider == 'yahoo':
                new_acct = YahooAccount(namespace=acct.namespace,
                                        password=acct.password,
                                        email_address=acct.email_address)
                db_session.add(new_acct)
            elif acct.provider == 'aol':
                new_acct = AOLAccount(namespace=acct.namespace,
                                      password=acct.password,
                                      email_address=acct.email_address)
                db_session.add(new_acct)
        db_session.commit()

    op.drop_table('genericaccount')
