"""
Integrity check debugging tool for IMAP accounts.

Run as:

    python -m inbox.util.consistency_check --help

"""
from __future__ import absolute_import, division, print_function

import argparse
import errno
import os
import pkg_resources
import subprocess
import sys

from fnmatch import fnmatch
from inbox.models import Account, Namespace
from inbox.models.session import session_scope
from inbox.sqlalchemy_ext.util import (
    b36_to_bin,
    int128_to_b36,  # XXX: should probably be called bin_to_b36
)

from .sqlite3_db import connect_sqlite3_db, init_sqlite3_db


class _ALL_ACCOUNTS(object):
    def __str__(self):
        return "all accounts"   # for --help


ALL_ACCOUNTS = _ALL_ACCOUNTS()


def execute_hooks(plugins, method_name):
    def f(*args, **kwargs):
        results = []
        for name, plugin in plugins:
            res = execute_hook(plugin, method_name)(*args, **kwargs)
            results.append(res)
        return results
    return f


def execute_hook(plugin, method_name):
    def f(*args, **kwargs):
        func = getattr(plugin, method_name, None)
        if func is None:
            return None
        return func(*args, **kwargs)
    return f


def main():
    # Load plugins
    group = 'inbox.consistency_check_plugins'
    plugins = []    # see ListPlugin as an example
    for entry_point in pkg_resources.iter_entry_points(group):
        plugin_factory = entry_point.load()     # usually a python class
        plugin = plugin_factory()
        plugins.append((entry_point.name, plugin))

    # Create argument parser
    # NOTE: In the future, the interface may change to accept namespace
    # public_ids instead of account public_ids.
    parser = argparse.ArgumentParser(
        description="""
        Shows differences between metadata fetched from the specified
        account(s) and what's stored in the local Inbox database.
        """,
        epilog = """
        Only Gmail accounts are currently supported.
        """)
    parser.add_argument(
        "public_ids", nargs='*', metavar="PUBLIC_ID",
        type=lambda x: int128_to_b36(b36_to_bin(x)), default=ALL_ACCOUNTS,
        help="account(s) to check (default: %(default)s)")
    parser.add_argument(
        '--cache-dir', default='./cache',
        help="cache directory (default: %(default)s)")
    parser.add_argument(
        '--no-overwrite', action='store_false', dest='force_overwrite',
        help="skip cache files already generated (default: overwrite them)")
    parser.add_argument(
        '--no-fetch', action='store_false', dest='do_slurp',
        help="don't fetch")
    parser.add_argument(
        '--no-dump', action='store_false', dest='do_dump',
        help="don't dump")
    parser.add_argument(
        '--no-diff', action='store_false', dest='do_diff',
        help="don't diff")
    execute_hooks(plugins, 'argparse_addoption')(parser)

    # Parse arguments
    args = parser.parse_args()
    execute_hooks(plugins, 'argparse_args')(args)

    # Make sure the cache directory exists.
    if not os.path.exists(args.cache_dir):
        os.mkdir(args.cache_dir)

    with session_scope() as db_session:
        # Query the list of accounts
        query = db_session.query(Account)
        if args.public_ids is not ALL_ACCOUNTS:
            query = query.filter(Account.public_id.in_(args.public_ids))
        accounts = query.all()

        # list.py uses this hook to show a list of accounts
        execute_hooks(plugins, 'process_accounts')(accounts)

        # hax
        if args.do_list:
            return

        # Query namespaces
        query = (
            db_session.query(Namespace, Account)
            .filter(Namespace.account_id == Account.id)
            .order_by(Namespace.id)
        )
        if args.public_ids is not ALL_ACCOUNTS:
            query = query.filter(Namespace.public_id.in_(args.public_ids))
        nnaa = query.all()

        # check for discrepancies
        missing_accounts = (set(a.public_id for ns, a in nnaa) ^
                            set(a.public_id for a in accounts))
        if missing_accounts:
            raise AssertionError("Missing accounts: %r" % (missing_accounts,))

        # Fetch metadata for each account and save it into a sqlite3 database
        # in the cache_dir.
        # - See imap_gm.py & local_gm.py
        # - See sqlite3_db.py for sqlite3 database schema.
        # This creates files like:
        # - cache/<account.public_id>.<namespace.public_id>.imap_gm.sqlite3
        # - cache/<account.public_id>.<namespace.public_id>.local_gm.sqlite3
        if args.do_slurp:
            for namespace, account in nnaa:
                can_slurp = execute_hooks(plugins, 'can_slurp_namespace')(
                    namespace=namespace,
                    account=account)
                for i, (plugin_name, plugin) in enumerate(plugins):
                    if not can_slurp[i]:
                        continue

                    db_path = os.path.join(
                        args.cache_dir,
                        cachefile_basename(
                            namespace=namespace,
                            account=account,
                            plugin_name=plugin_name,
                            ext='.sqlite3'))

                    if os.path.exists(db_path):
                        if not args.force_overwrite:
                            # already saved
                            print(
                                "skipping {0}: already exists".format(db_path),
                                file=sys.stderr)
                            continue
                        os.unlink(db_path)

                    db = init_sqlite3_db(connect_sqlite3_db(db_path))

                    with db:
                        execute_hook(plugin, 'slurp_namespace')(
                            namespace=namespace,
                            account=account,
                            db=db)

        # Generate canonical-format text files from the sqlite3 databases.
        # - See dump_gm.py
        # This creates files like:
        # - cache/<account.public_id>.<namespace.public_id>.imap_gm.txt
        # - cache/<account.public_id>.<namespace.public_id>.local_gm.txt
        if args.do_dump:
            for namespace, account in nnaa:
                can_dump = execute_hooks(plugins, 'can_dump_namespace')(
                    namespace=namespace,
                    account=account)
                for i, (plugin_name, plugin) in enumerate(plugins):
                    if not can_dump[i]:
                        continue

                    db_path = os.path.join(args.cache_dir, cachefile_basename(
                        namespace=namespace,
                        account=account,
                        plugin_name=plugin_name,
                        ext='.sqlite3'))

                    txt_path = os.path.join(args.cache_dir, cachefile_basename(
                        namespace=namespace,
                        account=account,
                        plugin_name=plugin_name,
                        ext='.txt'))

                    try:
                        db_stat = os.stat(db_path)
                    except OSError as e:
                        if e.errno != errno.ENOENT:
                            raise
                        db_stat = None
                    try:
                        txt_stat = os.stat(txt_path)
                    except OSError as e:
                        if e.errno != errno.ENOENT:
                            raise
                        txt_stat = None

                    if (db_stat and txt_stat and
                            db_stat.st_mtime < txt_stat.st_mtime):
                        print(
                            "skipping {0}: already exists".format(txt_path),
                            file=sys.stderr)
                        continue

                    db = connect_sqlite3_db(db_path)

                    with db, open(txt_path, "w") as txtfile:
                        execute_hook(plugin, 'dump_namespace')(
                            db=db,
                            txtfile=txtfile)

        # Show differences between the text files in the cache directory.
        # Basically, this runs something like the following for each account:
        #   vimdiff cache/${acct_pubid}.${ns_pubid).imap_gm.txt cache/${acct_pubid}.${ns_pubid).local_gm.txt
        if args.do_diff:
            if os.system("which vimdiff >/dev/null") == 0:
                diff_cmd = ['vimdiff']
            else:
                diff_cmd = ['diff', '-u']

            for namespace, account in nnaa:
                # plugins here would be nice here, too
                # This is such a hack
                files_to_diff = sorted(
                    os.path.join(args.cache_dir, f)
                    for f in os.listdir(args.cache_dir)
                    if fnmatch(f, cachefile_basename(
                        namespace=namespace,
                        account=account,
                        plugin_name='*',
                        ext='.txt')))
                if files_to_diff:
                    status = subprocess.call(diff_cmd + files_to_diff)
                    if status not in (0, 1):
                        raise AssertionError("error running diff")


def cachefile_basename(namespace, account, plugin_name, ext=''):
    return '{acct_pubid}.{ns_pubid}.{plugin_name}{ext}'.format(
        acct_pubid=account.public_id,
        ns_pubid=namespace.public_id,
        plugin_name=plugin_name,
        ext=ext)


if __name__ == '__main__':
    main()
