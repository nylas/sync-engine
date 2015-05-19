"""easaccount.username and easaccount.auth

Revision ID: 2f97277cd86d
Revises: 3cea90bfcdea
Create Date: 2014-10-04 07:59:29.540240

"""

# revision identifiers, used by Alembic.
revision = '2f97277cd86d'
down_revision = '3cea90bfcdea'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine()

    if not engine.has_table('easaccount'):
        return

    # We allow nullable=True because we don't have usernames for existing accounts.
    # Furthermore, we won't always get a username.
    from inbox.models.constants import MAX_INDEXABLE_LENGTH

    op.add_column('easaccount',
                  sa.Column('username', sa.String(255), nullable=True))

    op.add_column('easaccount',
                  sa.Column('eas_auth', sa.String(MAX_INDEXABLE_LENGTH),
                            nullable=True))

    Base = sa.ext.declarative.declarative_base()
    Base.metadata.reflect(engine)
    from inbox.models.session import session_scope

    class EASAccount(Base):
        __table__ = Base.metadata.tables['easaccount']

    with session_scope(versioned=False) as \
            db_session:
        accts = db_session.query(EASAccount).all()

        for a in accts:
            a.eas_auth = a.email_address
            db_session.add(a)

        db_session.commit()

    op.alter_column('easaccount', 'eas_auth', nullable=False,
                    existing_type=sa.String(MAX_INDEXABLE_LENGTH))


def downgrade():
    from inbox.ignition import main_engine
    engine = main_engine()

    if engine.has_table('easaccount'):
        op.drop_column('easaccount', 'username')
        op.drop_column('easaccount', 'eas_auth')
