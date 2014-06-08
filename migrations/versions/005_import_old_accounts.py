"""Import old accounts

Revision ID: adc646e1f11
Revises: 41a7e825d108
Create Date: 2014-03-17 19:00:27.631221

"""

# revision identifiers, used by Alembic.
revision = 'adc646e1f11'
down_revision = '41a7e825d108'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
import os.path


SQL_DUMP_FILENAME = 'alphasync_rds_inbox_imapaccount.sql'

def upgrade():
    from inbox.models import session_scope
    from inbox.models.ignition import engine
    from inbox.models.tables.imap import ImapAccount
    import inbox.auth.gmail as gmail

    # Assert we have the dump file
    if not os.path.isfile(SQL_DUMP_FILENAME):
        print "Can't find old user SQL dump at {0}...\nMigration no users."\
            .format(SQL_DUMP_FILENAME)
        return

    # Imports to `imapaccount_old` table
    with open(SQL_DUMP_FILENAME, 'r') as f:
        print 'Importing old account data...',
        op.execute(f.read())
        print 'OK!'

    Base = declarative_base()
    Base.metadata.reflect(engine)
    class ImapAccount_Old(Base):
        __table__ = Base.metadata.tables['imapaccount_old']


    with session_scope() as db_session:
        migrated_accounts = []

        for acct in db_session.query(ImapAccount_Old):
            print 'Importing {0}'. format(acct.email_address)

            existing_account = db_session.query(ImapAccount)\
                .filter_by(email_address=acct.email_address)
            if existing_account.count() > 0:
                print 'Already have account for {0}'. format(acct.email_address)
                continue

            # Create a mock OAuth response using data from the old table
            mock_response = dict(
                email=acct.email_address,
                issued_to=acct.o_token_issued_to,
                user_id=acct.o_user_id,
                access_token=acct.o_access_token,
                id_token=acct.o_id_token,
                expires_in=acct.o_expires_in,
                access_type=acct.o_access_type,
                token_type=acct.o_token_type,
                audience=acct.o_audience,
                scope=acct.o_scope,
                refresh_token=acct.o_refresh_token,
                verified_email=acct.o_verified_email
                )

            new_account = gmail.create_account(db_session, acct.email_address, mock_response)

            # Note that this doesn't verify **anything** about the account.
            # We're just doing the migration now
            db_session.add(new_account)
            db_session.commit()
            migrated_accounts.append(new_account)

        print '\nDone! Imported {0} accounts.'.format(len(migrated_accounts))
        print '\nNow verifying refresh tokens...\n'

        verified_accounts = []
        for acct in migrated_accounts:
            try:
                print 'Verifying {0}... '.format(acct.email_address),
                gmail.verify_account(db_session, acct)
                verified_accounts.append(acct)
                print 'OK!'
            except Exception, e:
                print 'FAILED!', e

        print 'Done! Verified {0} of {1}'.format(len(verified_accounts), len(migrated_accounts))

    op.drop_table('imapaccount_old')


def downgrade():
    print 'Not removing any accounts!'
