import sys

from inbox.models.session import session_scope
from inbox.models.account import Account
from inbox.log import safe_format_exception


def report_killed(account_id, folder_name=None):
    error = safe_format_exception(*sys.exc_info())

    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)

        # MailSyncMonitor for account
        if folder_name is None:
            account.kill_sync(error)
        else:
            # FolderSyncMonitor for account's folder
            statuses = account.foldersyncstatuses
            for f in statuses:
                if f.folder.name == folder_name:
                    f.kill_sync(error)

            if all([f.is_killed for f in statuses]):
                account.kill_sync()

        db_session.commit()
