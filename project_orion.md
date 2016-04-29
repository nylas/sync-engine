set -e

# Intalling the sync engine without a VM on OS X 10.11

## Set up a virtualenv

    virtualenv --no-site-packages --clear .
    source bin/activate

    git clone git://github.com/lxml/lxml.git lxml

    pip install -r requirements.txt

## Install lxml

    cd lxml

    STATIC_DEPS=true LIBXML2_VERSION=2.9.2 python setup.py install --static-deps

## (optional) Verify lxml is installed properly

    python -c 'import lxml'
    python -c 'from lxml import etree'

    cd ..

<!-- ldd /Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/site-packages/lxml/etree.so
That will show if you have any unresolved shared libraries. You may need to install/update some packages. -->


## Install Gevent
Apple changed the default CFLAGS to 'c11' on 10.11 so you have to set it
manually back to 'c99' in order to build gevent

    CFLAGS='-std=c99' pip install gevent

## Install IMAP sync engine
    pip install -e .  # sync-engine

## Install EAS code

    git clone git@github.com:nylas/sync-engine-eas.git eas
    cd eas
    pip install -e .
    cd ./


## Install Redis in the virtualenv (currently needed for scheduler)

    ./install_redis_local.sh


## Start Redis
    ./bin/redis-server &

## Clear weird script modifications
    git checkout bin

Go modify `sync-engine/inbox/ignition.py` for a lo

## Create the database
    INBOX_CFG_PATH=etc/config-dev.json:etc/secrets-dev.yml bin/create-db

## Auth an account
    INBOX_CFG_PATH=etc/config-dev.json:etc/secrets-dev.yml bin/inbox-auth mgrinich@gmail.com

## Start the sync server
    INBOX_CFG_PATH=etc/config-dev.json:etc/secrets-dev.yml bin/inbox-start

## Start the API on port 7777
    INBOX_CFG_PATH=etc/config-dev.json:etc/secrets-dev.yml bin/inbox-api --port 7777


It works! But there are some bugs

- There are some issues with SQlite not auto-incrementing columns which are not the primary key in the table.

- Other greenlet blocking?
