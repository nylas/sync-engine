"""Revert EAS passwords.

Revision ID: 3e78582b4163
Revises: 2b89164aa9cd
Create Date: 2014-09-06 17:33:37.370462

"""

# revision identifiers, used by Alembic.
revision = '3e78582b4163'
down_revision = '2b89164aa9cd'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = sa.ext.declarative.declarative_base()
    Base.metadata.reflect(engine)
    from inbox.models.session import session_scope

    if 'easaccount' in Base.metadata.tables:
        op.add_column('easaccount', 'password')

        class EASAccount(Base):
            __table__ = Base.metadata.tables['easaccount']

        class Secret(Base):
            __table__ = Base.metadata.tables['secret']

        with session_scope(ignore_soft_deletes=False, versioned=False) as \
                db_session:
            accounts = db_session.query(EASAccount).all()

            for a in accounts:
                secret_id = a.password_id

                # Have already been decrypted, so directly set
                secret = db_session.query(Secret).get(secret_id)
                a.password = secret.secret

                db_session.add(a)

        db_session.commit()

        op.drop_column('easaccount', 'password_id')


def downgrade():
    pass
