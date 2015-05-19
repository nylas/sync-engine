"""generic_imap

Revision ID: 43cd2de5ad85
Revises: 2525c5245cc2
Create Date: 2014-08-01 14:36:09.980388

"""

# revision identifiers, used by Alembic.
revision = '43cd2de5ad85'
down_revision = '4e93522b5b62'

from alembic import op
import sqlalchemy as sa
from datetime import datetime


def upgrade():
    from inbox.models.session import session_scope
    from sqlalchemy.ext.declarative import declarative_base
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
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

    class ImapAccount(Base):
        __table__ = Base.metadata.tables['imapaccount']

    class YahooAccount(Base):
        __table__ = Base.metadata.tables['yahooaccount']

    class AOLAccount(Base):
        __table__ = Base.metadata.tables['aolaccount']

    class GenericAccount(Base):
        __table__ = Base.metadata.tables['genericaccount']

    class Secret(Base):
        __table__ = Base.metadata.tables['secret']

    with session_scope(versioned=False) \
            as db_session:
        for acct in db_session.query(YahooAccount):
            secret = Secret(acl_id=0, type=0, secret=acct.password,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow())
            db_session.add(secret)
            db_session.commit()

            new_acct = GenericAccount(id=acct.id,
                                      provider='yahoo')

            new_acct.password_id = secret.id
            db_session.add(new_acct)

        for acct in db_session.query(AOLAccount):
            secret = Secret(acl_id=0, type=0, secret=acct.password,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow())
            db_session.add(secret)
            db_session.commit()

            new_acct = GenericAccount(id=acct.id,
                                      provider='aol')

            new_acct.password_id = secret.id
            db_session.add(new_acct)

        db_session.commit()

    # don't cascade the delete
    engine.execute("drop table aolaccount")
    engine.execute("drop table yahooaccount")
    op.drop_column('imapaccount', 'imap_host')


def downgrade():
    from inbox.models.session import session_scope
    from sqlalchemy.ext.declarative import declarative_base
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
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

    class ImapAccount(Base):
        __table__ = Base.metadata.tables['imapaccount']

    class YahooAccount(Base):
        __table__ = Base.metadata.tables['yahooaccount']

    class AOLAccount(Base):
        __table__ = Base.metadata.tables['aolaccount']

    class GenericAccount(Base):
        __table__ = Base.metadata.tables['genericaccount']

    with session_scope(versioned=False) \
            as db_session:
        for acct in db_session.query(GenericAccount):
            secret = db_session.query(Secret) \
                .filter_by(id=acct.password_id).one()

            if acct.provider == 'yahoo':
                new_acct = YahooAccount(namespace=acct.namespace,
                                        password=secret.secret)
                db_session.add(new_acct)
            elif acct.provider == 'aol':
                new_acct = AOLAccount(namespace=acct.namespace,
                                      password=secret.secret)
                db_session.add(new_acct)
        db_session.commit()

    engine.execute('drop table genericaccount')
