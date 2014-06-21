def account_status(db_session, account, and_folders=False):
    folders_info = folder_statuses(db_session, account)
    acct_info = dict(id=account.id,
                     email=account.email_address,
                     provider=account.provider,
                     state=account.sync_active)
    if and_folders:
        return [acct_info, folders_info]
    else:
        return acct_info


def folder_statuses(db_session, account):
    return [foldersync.sync_status for foldersync in account.foldersyncs]
