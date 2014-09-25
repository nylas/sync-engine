from __future__ import absolute_import, division, print_function

# setup.py boilerplate for this plugin:
#
# entry_points={
#     'inbox.consistency_check_plugins': [
#         'list = inbox.util.consistency_check.list:ListPlugin',
#     ],
# },


class ListPlugin(object):
    def argparse_addoption(self, parser):
        parser.add_argument(
            '--list', action='store_true', dest='do_list',
            help="print a tab-separated list of accounts to stdout")

    def argparse_args(self, args):
        self.args = args

    def process_accounts(self, accounts):
        # If the --list argument was specified, print the list of accounts.
        if not self.args.do_list:
            return
        for account in accounts:
            print("\t".join([
                str(account.id),
                account.public_id,
                account.email_address,
                account.provider,
                account.__tablename__,
            ]))
