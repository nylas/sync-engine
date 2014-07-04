from datetime import datetime

from inbox.models.session import session_scope
from inbox.models.account import Account


def report_exit(state, account_id=None, folder_name=None):
    if account_id is not None:
        assert state in ('stopped', 'killed')

        with session_scope() as db_session:
            account = db_session.query(Account).get(account_id)

            if folder_name is None:
                # MailSyncMonitor for account
                account.sync_host = None
                account.sync_state = state
                account.sync_end_time = datetime.utcnow()
            else:
                # FolderSyncMonitor for account's folder
                for f in account.foldersyncs:
                    if f.folder_name == folder_name:
                        f.update_sync_status(
                            dict(run_state=state,
                                 sync_end_time=datetime.utcnow()))

            db_session.commit()
