from setuptools import setup, find_packages

setup(
    name = "inbox",
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

    author = "Inbox Team",
    author_email = "admin@inboxapp.com",
    description = "The Inbox AppServer",
    license = "AGPLv3",
    keywords = "inbox app appserver email",
    url = "https://www.inboxapp.com",
)
