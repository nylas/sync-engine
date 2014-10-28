"""EAS two-devices turn

Revision ID: 17dc9c049f8b
Revises: ad7b856bcc0
Create Date: 2014-10-21 20:38:14.311747

"""

# revision identifiers, used by Alembic.
revision = '17dc9c049f8b'
down_revision = 'ad7b856bcc0'

from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine()

    if not engine.has_table('easaccount'):
        return

    from inbox.models.session import session_scope

    Base = sa.ext.declarative.declarative_base()
    Base.metadata.reflect(engine)

    class EASAccount(Base):
        __table__ = Base.metadata.tables['easaccount']
        primary_device = sa.orm.relationship(
        'EASDevice', primaryjoin='and_(EASAccount.primary_device_id == EASDevice.id, '
        'EASDevice.deleted_at.is_(None))', uselist=False)
        secondary_device = sa.orm.relationship(
        'EASDevice', primaryjoin='and_(EASAccount.secondary_device_id == EASDevice.id, '
        'EASDevice.deleted_at.is_(None))', uselist=False)

    class EASDevice(Base):
        __table__ = Base.metadata.tables['easdevice']

    with session_scope(ignore_soft_deletes=False, versioned=False) as \
            db_session:

        accts = db_session.query(EASAccount).all()

        for a in accts:
            # Set both to filtered=False, //needed// for correct deploy.
            primary = EASDevice(created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow(),
                                filtered=False,
                                eas_device_id=a._eas_device_id,
                                eas_device_type=a._eas_device_type,
                                eas_policy_key=a.eas_policy_key,
                                eas_sync_key=a.eas_account_sync_key)

            secondary = EASDevice(created_at=datetime.utcnow(),
                                  updated_at=datetime.utcnow(),
                                  filtered=False,
                                  eas_device_id=a._eas_device_id,
                                  eas_device_type=a._eas_device_type,
                                  eas_policy_key=a.eas_policy_key,
                                  eas_sync_key=a.eas_account_sync_key)

            a.primary_device = primary
            a.secondary_device = secondary

            db_session.add(a)

        db_session.commit()

    conn = op.get_bind()

    acct_device_map = dict(
        (id_, device_id) for id_, device_id in conn.execute(text(
            """SELECT id, secondary_device_id from easaccount""")))

    print 'acct_device_map: ', acct_device_map

    for acct_id, device_id in acct_device_map.iteritems():
        conn.execute(text("""
            UPDATE easfoldersyncstatus
            SET device_id=:device_id
            WHERE account_id=:acct_id
            """), device_id=device_id, acct_id=acct_id)

        conn.execute(text("""
            UPDATE easuid
            SET device_id=:device_id
            WHERE easaccount_id=:acct_id
            """), device_id=device_id, acct_id=acct_id)


def downgrade():
    raise Exception('!')
