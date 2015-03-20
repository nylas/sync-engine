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
        "SQLAlchemy==0.9.8",
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
        "python-dateutil>=2.4",
        "ipython>=1.0.0",
        "enum34==1.0.4",
        "gdata>=2.0.18",
        "simplejson>=3.6.0",
        "geventconnpool>=0.2.1",
        "icalendar>=3.8.2",
        "simplejson>=3.6.0",
        "imapclient>=0.11",
        "Flask>=0.10.1",
        "futures>=2.1.3",
        "Flask-RESTful>=0.3.2",
        "pynacl>=0.2.3",
        "flanker>=0.4.26",
        "httplib2>=0.8",
        "six>=1.8",
        "vobject>=0.8.1c",
        "lxml>=3.4.2",
        "arrow==0.5.4"
    ],
    dependency_links=[],

    include_package_data=True,
    package_data={
        # "inbox-sync": ["alembic.ini"],
        # If any package contains *.txt or *.rst files, include them:
        # '': ['*.txt', '*.rst'],
        # And include any *.msg files found in the 'hello' package, too:
        # 'hello': ['*.msg'],
    },
    data_files=[("alembic-inbox-sync", ["alembic.ini"]),
                ("alembic-inbox-sync/migrations",
                 filter(os.path.isfile, glob.glob("migrations/*"))),
                ("alembic-inbox-sync/migrations/versions",
                 filter(os.path.isfile, glob.glob("migrations/versions/*")))
                ],

    scripts=['bin/inbox-start',
             'bin/inbox-console',
             'bin/search-index-service',
             'bin/migrate-participant-format',
             'bin/backfill-emailed-events',
             'bin/create-emailed-events-calendar.py',
             'bin/start-stop-account',
             'bin/inbox-auth',
             'bin/regen-labels',
             'bin/delete-account',
             'bin/alive-dead-metrics',
             'bin/syncback-service'],

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
    },
    zip_safe=False,
    author="Inbox Team",
    author_email="admin@inboxapp.com",
    description="The Inbox AppServer",
    license="AGPLv3",
    keywords="inbox app appserver email",
    url="https://www.inboxapp.com",
)
