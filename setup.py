from setuptools import setup, find_packages

setup(
    name = "inbox-sync",
    version = "0.1",
    packages = find_packages(),

    install_requires = [],
    dependency_links = [],

    package_data = {
        # If any package contains *.txt or *.rst files, include them:
        # '': ['*.txt', '*.rst'],
        # And include any *.msg files found in the 'hello' package, too:
        # 'hello': ['*.msg'],
    },

    # See:
    # https://pythonhosted.org/setuptools/setuptools.html#dynamic-discovery-of-services-and-plugins
    # https://pythonhosted.org/setuptools/pkg_resources.html#entry-points
    entry_points = {
        # See https://pythonhosted.org/setuptools/setuptools.html#automatic-script-creation
        #'console_scripts': [
        #    'inbox-consistency-check = inbox.util.consistency_check.__main__:main',
        #],

        # See inbox/util/consistency_check/__main__.py
        'inbox.consistency_check_plugins': [
            'list = inbox.util.consistency_check.list:ListPlugin',
            'imap_gm = inbox.util.consistency_check.imap_gm:ImapGmailPlugin',
            'local_gm = inbox.util.consistency_check.local_gm:LocalGmailPlugin',
        ],
    },

    author = "Inbox Team",
    author_email = "admin@inboxapp.com",
    description = "The Inbox AppServer",
    license = "AGPLv3",
    keywords = "inbox app appserver email",
    url = "https://www.inboxapp.com",
)
