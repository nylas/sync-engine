#!/usr/bin/env python
# We previously didn't store IMAP path separators for generic imap accounts.
# This script backfixes the accounts.
import click

from inbox.crispin import connection_pool

from nylas.logging import get_logger, configure_logging
from inbox.models.backends.generic import GenericAccount
from inbox.models.session import (session_scope, global_session_scope,
                                  session_scope_by_shard_id)

configure_logging()
log = get_logger(purpose='separator-backfix')

@click.command()
@click.option('--min-id', type=int, default=None)
@click.option('--max-id', type=int, default=None)
@click.option('--shard-id', type=int, default=None)
def main(min_id, max_id, shard_id):
    generic_accounts = []
    failed = []

    if min_id is not None or max_id is not None:
        # Get the list of running Gmail accounts.
        with global_session_scope() as db_session:
            generic_accounts = db_session.query(GenericAccount).filter(
                GenericAccount.sync_state == 'running')

            if min_id is not None:
                generic_accounts = generic_accounts.filter(
                    GenericAccount.id > min_id)

            if max_id is not None:
                generic_accounts = generic_accounts.filter(
                    GenericAccount.id <= max_id)

            generic_accounts = [acc.id for acc in generic_accounts]

            db_session.expunge_all()

    elif shard_id is not None:
        with session_scope_by_shard_id(shard_id) as db_session:
            generic_accounts = db_session.query(GenericAccount).filter(
                GenericAccount.sync_state == 'running')

            generic_accounts = [acc.id for acc in generic_accounts]
            db_session.expunge_all()

    print "Total accounts: %d" % len(generic_accounts)

    for account_id in generic_accounts:
        try:
            with session_scope(account_id) as db_session:
                account = db_session.query(GenericAccount).get(account_id)
                print "Updating %s" % account.email_address

                with connection_pool(account.id).get() as crispin_client:
                    account.folder_prefix = crispin_client.folder_prefix
                    account.folder_separator = crispin_client.folder_separator

                db_session.commit()
        except Exception:
            failed.append(account_id)

    print "Processed accounts:"
    print generic_accounts

    print "Failed accounts:"
    print failed

if __name__ == '__main__':
    main()
