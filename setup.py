import glob
import os
from setuptools import setup, find_packages


setup(
    name="inbox-sync",
    version="0.4",
    packages=find_packages(),

    install_requires=[
        "gevent>=1.0.1",
        "click>=2.4",
        "cpu_affinity>=0.1.0",
        "pyyaml",
        "SQLAlchemy>=0.9.6",
        "alembic>=0.6.4",
        "requests>=2.4.3",
        "raven>=5.0.0",
        "colorlog>=1.8",
        "structlog>=0.4.1",
        "html2text>=2014.9.8",
        "pyinstrument>=0.12",
        "PyMySQL>=0.6.2",
        "elasticsearch>=1.2.0",
        "setproctitle>=1.1.8",
        "pymongo>=2.5.2",
        "python-dateutil>=2.3",
        "enum>=0.4.4",
        "gdata>=2.0.18",
        "simplejson>=3.6.0",
        "geventconnpool>=0.2.1",
        "icalendar>=3.8.2",
        "simplejson>=3.6.0",
        "imapclient>=0.11",
        "Flask>=0.10.1",
        "futures>=2.1.3",
        "Flask-RESTful>=0.2.12",
        "pynacl==0.3.0",
        "flanker>=0.4.26",
        "httplib2>=0.8",
        "google-api-python-client>=1.2",
        "oauth2client==1.3",
        "six>=1.8"
    ],
    dependency_links=[],

    include_package_data=True,
    package_data={
        #"inbox-sync": ["alembic.ini"],
        # If any package contains *.txt or *.rst files, include them:
        # '': ['*.txt', '*.rst'],
        # And include any *.msg files found in the 'hello' package, too:
        # 'hello': ['*.msg'],
    },
    data_files=[(".", ["alembic.ini"]),
                ("migrations", filter(os.path.isfile,
                                      glob.glob("migrations/*"))),
                ("migrations/versions",
                 filter(os.path.isfile, glob.glob("migrations/versions/*")))
                ],

    scripts=['bin/inbox-start', 'bin/search-index-service', 'bin/syncback-service'],

    # See:
    # https://pythonhosted.org/setuptools/setuptools.html#dynamic-discovery-of-services-and-plugins
    # https://pythonhosted.org/setuptools/pkg_resources.html#entry-points
    entry_points={
        # See https://pythonhosted.org/setuptools/setuptools.html#automatic-script-creation
        # 'console_scripts': [
        #     'inbox-consistency-check = inbox.util.consistency_check.__main__:main',
        # ],

        # See inbox/util/consistency_check/__main__.py
        'inbox.consistency_check_plugins': [
            'list=inbox.util.consistency_check.list:ListPlugin',
            'imap_gm=inbox.util.consistency_check.imap_gm:ImapGmailPlugin',
            'local_gm=inbox.util.consistency_check.local_gm:LocalGmailPlugin',
        ],

        # See inbox/providers.py
        # 'inbox.providers': [],

        # Pluggable auth providers.  See inbox/auth/__init__.py
        'inbox.auth': [
            'generic = inbox.auth.generic:GenericAuthHandler',
            'gmail = inbox.auth.gmail:GmailAuthHandler',
            # 'oauth = inbox.auth.oauth:OAuthAuthHandler',
            'outlook = inbox.auth.outlook:OutlookAuthHandler',
        ],

        # Pluggable auth provider mixins.  See inbox/auth/__init__.py
        # 'inbox.auth.mixins': [],
    },
    zip_safe=False,
    author="Inbox Team",
    author_email="admin@inboxapp.com",
    description="The Inbox AppServer",
    license="AGPLv3",
    keywords="inbox app appserver email",
    url="https://www.inboxapp.com",
)
