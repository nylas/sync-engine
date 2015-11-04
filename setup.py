import glob
import os
from setuptools import setup, find_packages


setup(
    name="inbox-sync",
    version="0.4",
    packages=find_packages(),

    install_requires=[
        "gevent>=1.0.1",
        "nylas-production-python>=0.2.0",
        "click>=2.4",
        "cpu_affinity>=0.1.0",
        "pyyaml",
        "SQLAlchemy==1.0.6",
        "alembic>=0.6.4",
        "requests>=2.4.3",
        "html2text>=2014.9.8",
        "pyinstrument>=0.12",
        "PyMySQL>=0.6.2",
        "mysqlclient==1.3.6",
        "setproctitle>=1.1.8",
        "pymongo>=2.5.2",
        "python-dateutil>=2.4",
        "ipython>=1.0.0",
        "enum34==1.0.4",
        "gdata>=2.0.18",
        "simplejson>=3.6.0",
        "icalendar>=3.8.2",
        "simplejson>=3.6.0",
        "imapclient>=0.13",
        "Flask>=0.10.1",
        "Flask-RESTful==0.3.2",
        "pynacl>=0.2.3",
        "flanker>=0.4.26",
        "httplib2>=0.8",
        "six>=1.8",
        "vobject>=0.8.1c",
        "lxml>=3.4.2",
        "arrow==0.5.4",
        "statsd>=3.1",
        "boto3>=1.1.4",
        "Pympler==0.4.2"
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
             'bin/migrate-account',
             'bin/migrate-account-bulk',
             'bin/summary-stats',
             'bin/start-stop-account',
             'bin/inbox-auth',
             'bin/delete-account-data',
             'bin/alive-dead-metrics',
             'bin/create-db',
             'bin/create-test-db',
             'bin/verify-db',
             'bin/inbox-api',
             'bin/get-id',
             'bin/get-object',
             'bin/syncback-service',
             'bin/contact-search-service',
             'bin/contact-search-backfill',
             'bin/contact-search-delete-index',
             ],

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
    author="Nylas Team",
    author_email="team@nylas.com",
    description="The Nylas Sync Engine",
    license="AGPLv3",
    keywords="nylas",
    url="https://www.nylas.com",
)
