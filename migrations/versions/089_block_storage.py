"""Block storage

Revision ID: 43e5867a6ef1
Revises: 1683790906cf
Create Date: 2014-08-21 18:19:26.851250

"""

# revision identifiers, used by Alembic.
revision = '43e5867a6ef1'
down_revision = '1683790906cf'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('block', sa.Column('encryption_scheme', sa.Integer(),
                  server_default='0', nullable=False))

    from inbox.ignition import main_engine
    from inbox.models.session import session_scope

    engine = main_engine(pool_size=1, max_overflow=0)
    Base = sa.ext.declarative.declarative_base()
    Base.metadata.reflect(engine)

    class Block(Base):
        __table__ = Base.metadata.tables['block']

    with session_scope(ignore_soft_deletes=False, versioned=False) as \
            db_session:
        count = db_session.query(Block).update({'encryption_scheme': 0})

        print 'Updated {0} blocks'.format(count)

        db_session.commit()


def downgrade():
    raise Exception('No.')
