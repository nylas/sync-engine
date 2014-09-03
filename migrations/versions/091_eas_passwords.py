"""EAS passwords

Revision ID: 31dc0411eecf
Revises: 24e9afe91349
Create Date: 2014-09-03 07:22:00.476690

"""

# revision identifiers, used by Alembic.
revision = '31dc0411eecf'
down_revision = '24e9afe91349'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = sa.ext.declarative.declarative_base()
    Base.metadata.reflect(engine)
    from inbox.models.session import session_scope
    from inbox.models.secret import Secret

    if 'easaccount' in Base.metadata.tables:
        op.add_column('easaccount', sa.Column('password_id', sa.Integer()))

        class EASAccount(Base):
            __table__ = Base.metadata.tables['easaccount']

        with session_scope(ignore_soft_deletes=False, versioned=False) as \
                db_session:
            accounts = db_session.query(EASAccount).all()
            print '# EAS accounts: ', len(accounts)

            for a in accounts:
                value = a.password

                if isinstance(value, unicode):
                    value = value.encode('utf-8')

                if b'\x00' in value:
                    print 'Invalid password for account_id: {0}, skipping'.\
                        format(a.id)
                    continue

                secret = Secret()
                secret.secret = value
                secret.type = 'password'

                a.password_id = secret.id

                db_session.add(secret)
                db_session.add(a)

                assert a.password == value

        db_session.commit()

        op.drop_column('easaccount', 'password')


def downgrade():
    raise Exception('Would create insecurities.')
