import sys

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        # only run tests from tests/
        self.test_args = ['-s', '-x', 'tests']
        self.test_suite = True
    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)

setup(
    name = "inbox",
    version = "0.1",
    packages = find_packages(),
    scripts = ['inboxapp-srv'],

    install_requires = [
        "argparse==1.2.1",
        "beautifulsoup4==4.1.3",
        "httplib2==0.8",
        "pytest==2.3.4",
        "tornado==3.0.1",
        "wsgiref==0.1.2",
        "futures==2.1.3",
        "jsonrpclib==0.1.3",
        "SQLAlchemy==0.8.3",
        "pymongo==2.5.2",  # For json_util in bson
        "dnspython==1.11.0",
        "boto==2.10.0",
        "ipython==1.0.0",
        "Flask==0.10.1",
        "gevent-socketio==0.3.5-rc2",
        "gunicorn==17.5",
        "colorlog==1.8",
        "MySQL-python==1.2.4",
        "requests==2.0.0",
        "Fabric==1.7.0",
        "supervisor==3.0",
        "iconv==1.0",
        "chardet==2.1.1",
        "PIL==1.1.7",
        "Wand==0.3.5",
        "setproctitle==1.1.7",
        # For ZeroRPC
        "Cython==0.19.1",
        "zerorpc==0.4.3",
        # TODO add xapian (for search) - not on PyPI yet
        ],
    dependency_links = [
        # Our own versions of these
        "git+git://github.com/inboxapp/imapclient#egg=imapclient",
        "git+git://github.com/inboxapp/bleach#egg=bleach",
        "git+git://github.com/dotcloud/zerorpc-python.git#egg=zerorpc",
        # v13.1.0
        "git+git://github.com/zeromq/pyzmq.git@v13.1.0#egg=zmq",
        ],

    package_data = {
        # If any package contains *.txt or *.rst files, include them:
        # '': ['*.txt', '*.rst'],
        # And include any *.msg files found in the 'hello' package, too:
        # 'hello': ['*.msg'],
    },

    author = "Inbox Team",
    author_email = "admin@inboxapp.com",
    description = "The Inbox AppServer",
    license = "Proprietary",
    keywords = "inbox app appserver email",
    url = "http://www.inboxapp.com",

    # could also include long_description, download_url, classifiers, etc.
    tests_require=['pytest'],
    cmdclass = {'test': PyTest},
)
