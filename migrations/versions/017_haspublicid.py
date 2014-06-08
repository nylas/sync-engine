"""HasPublicID

Revision ID: 2c9f3a06de09
Revises: 5093433b073
Create Date: 2014-04-26 04:05:57.715053

"""

from __future__ import division

# revision identifiers, used by Alembic.
revision = '2c9f3a06de09'
down_revision = '5093433b073'

import sys
from gc import collect as garbage_collect

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


chunk_size = 500


def upgrade():
    from inbox.sqlalchemy_ext.util import generate_public_id
    from inbox.models import session_scope

    # These all inherit HasPublicID
    from inbox.models.tables.base import (
        Account, Block, Contact, Message, Namespace,
        SharedFolder, Thread, User, UserSession, HasPublicID)

    classes = [
        Account, Block, Contact, Message, Namespace,
        SharedFolder, Thread, User, UserSession]

    for c in classes:
        assert issubclass(c, HasPublicID)
        print '[{0}] adding public_id column... '.format(c.__tablename__),
        sys.stdout.flush()
        op.add_column(c.__tablename__, sa.Column(
            'public_id', mysql.BINARY(16), nullable=False))

        print 'adding index... ',
        op.create_index(
            'ix_{0}_public_id'.format(c.__tablename__),
            c.__tablename__,
            ['public_id'],
            unique=False)

        print 'Done!'
        sys.stdout.flush()

    print 'Finished adding columns. \nNow generating public_ids'

    with session_scope() as db_session:
        count = 0
        for c in classes:
            garbage_collect()
            print '[{0}] Loading rows. '.format(c.__name__),
            sys.stdout.flush()
            print 'Generating public_ids',
            sys.stdout.flush()
            for r in db_session.query(c).yield_per(chunk_size):
                count += 1
                r.public_id = generate_public_id()
                if not count % chunk_size:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    db_session.commit()
                    garbage_collect()
            sys.stdout.write(' Saving. '.format(c.__name__)),
            # sys.stdout.flush()
            sys.stdout.flush()
            db_session.commit()
            sys.stdout.write('Done!\n')
            sys.stdout.flush()
        print '\nUpdgraded OK!\n'


def downgrade():
    # These all inherit HasPublicID
    from inbox.models.tables.base import (
        Account, Block, Contact, Message, Namespace,
        SharedFolder, Thread, User, UserSession, HasPublicID)

    classes = [
        Account, Block, Contact, Message, Namespace,
        SharedFolder, Thread, User, UserSession]

    for c in classes:
        assert issubclass(c, HasPublicID)
        print '[{0}] Dropping public_id column... '.format(c.__tablename__),
        op.drop_column(c.__tablename__, 'public_id')

        print 'Dropping index... ',
        op.drop_index(
            'ix_{0}_public_id'.format(c.__tablename__),
            table_name=c.__tablename__)

        print 'Done.'
