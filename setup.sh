#!/bin/bash

set -e

configure_db=true
while getopts "p" opt; do
    case $opt in
        p)
            configure_db=false
        ;;
    esac
done

color() {
      printf '\033[%sm%s\033[m\n' "$@"
      # usage color "31;5" "string"
      # 0 default
      # 5 blink, 1 strong, 4 underlined
      # fg: 31 red,  32 green, 33 yellow, 34 blue, 35 purple, 36 cyan, 37 white
      # bg: 40 black, 41 red, 44 blue, 45 purple
      }

color '36;1' "
      _____       _
     |_   _|     | |
       | |  _ __ | |__   _____  __
       | | | '_ \| '_ \ / _ \ \/ /
      _| |_| | | | |_) | (_) >  <
     |_____|_| |_|_.__/ \___/_/\_\\

     This script installs dependencies for Inbox.

     For more details, visit:
     https://www.github.com/inboxapp/inbox
"

if [ ! -f "/usr/include/sodium.h" ]; then
color '35;1' 'Installing sodium crypto library'
    mkdir -p setup
    cd setup
    libsodium=libsodium-0.7.0.tar.gz
    if [ ! -f $libsodium ]; then
        color '34;1' ' > Downloading...'
        wget -q -O "$libsodium" https://download.libsodium.org/libsodium/releases/$libsodium
    fi

    color '34;1' ' > Checking the hash...'
    if ! shasum -a 256 -s -c << EOF
        4ccaffd1a15be67786e28a61b602492a97eb5bcb83455ed53c02fa038b8e9168 *$libsodium
EOF
    then
        color '31;1' " Error verifying $libsodium hash!"
        exit 1
    else
        color '32;1' " $libsodium hash ok."
    fi

    tar -zxf $libsodium
    pushd `pwd`
    cd ${libsodium//.tar.gz/}
    color '34;1' ' > Configuring...'
    ./configure --prefix=/usr --quiet
    color '34;1' ' > Building...'
    make -s > /tmp/$libsodium.build.out
    color '34;1' ' > Installing...'
    make install -s > /tmp/$libsodium.build.out
    popd
    color '34;1' ' > Cleaning up'
    rm -fr setup $libsodium
    color '34;1' ' > libsodium installation done.'
fi

color '35;1' 'Updating packages...'
apt-get update
apt-get -y install python-software-properties

# Preconfigure MySQL root password
echo "mysql-server mysql-server/root_password password root" | debconf-set-selections
echo "mysql-server mysql-server/root_password_again password root" | debconf-set-selections

color '35;1' 'Installing dependencies from apt-get...'
apt-get -y install git \
                   wget \
                   supervisor \
                   mysql-server \
                   mysql-client \
                   python \
                   python-dev \
                   python-pip \
                   python-setuptools \
                   build-essential \
                   libmysqlclient-dev \
                   gcc \
                   g++ \
                   libzmq-dev \
                   libxml2-dev \
                   libxslt-dev \
                   lib32z1-dev \
                   libffi-dev \
                   python-lxml \
                   tmux \
                   curl \
                   tnef \

color '35;1' 'Installing dependencies from pip...'
pip install --upgrade setuptools
pip install -r requirements.txt

pip install -e .
if [ -d "../inbox-eas" ]; then
    pip install -r ../inbox-eas/requirements.txt
    pip install -e ../inbox-eas
fi

color '35;1' 'Finished installing dependencies.'

mkdir -p /etc/inboxapp
chown $SUDO_USER /etc/inboxapp

color '35;1' 'Copying default development configuration to /etc/inboxapp'
src=./etc/config-dev.json
dest=/etc/inboxapp/config.json
if [ ! -f $dest ]; then
    cp $src $dest
elif [ $src -nt $dest ]; then
    set +e
    diff_result=$(diff -q $src $dest)
    different=$?
    set -e
    if [ $different -ne 0 ]; then
        echo "Error: inbox config is newer and merging of configs not (yet) supported."
        echo "Diffs:"
        echo "src: $src dest: $dest"
        diff $dest $src
        exit 1
    fi
fi

color '35;1' 'Copying default secrets configuration to /etc/inboxapp'
src=./etc/secrets-dev.yml
dest=/etc/inboxapp/secrets-dev.yml
if [ ! -f $dest ]; then
    cp $src $dest
elif [ $src -nt $dest ]; then
    set +e
    diff_result=$(diff -q $src $dest)
    different=$?
    set -e
    if [ $different -ne 0 ]; then
        echo "Error: inbox secrets config is newer and merging of configs not (yet) supported."
        echo "Diffs:"
        echo "src: $src dest: $dest"
        diff $dest $src
        exit 1
    fi
fi

if $configure_db; then
    # Mysql config
    color '35;1' 'Copying default mysql configuration to /etc/mysql/conf.d'
    src=./etc/my.cnf
    dest=/etc/mysql/conf.d/inboxapp.cnf
    if [ ! -f $dest ]; then
        cp $src $dest
    elif [ $src -nt $dest ]; then
        set +e
        diff_result=$(diff -q $src $dest)
        different=$?
        set -e
        if [ $different -ne 0 ]; then
            echo "Error: inbox config is newer and merging of configs not (yet) supported."
            echo "Diffs:"
            echo "src: $src dest: $dest"
            diff $dest $src
            exit 1
        fi
    fi

    mysqld_safe &
    sleep 10

    db_name=`cat /etc/inboxapp/config.json  | grep "MYSQL_DATABASE" | awk '{ print $2 }' | sed "s/\"\(.*\)\",/\1/"`
    if ! have_dbs=$(mysql -e "show databases like '$db_name'" | grep -q $db_name); then
        color '35;1' 'Creating databases...'
        python bin/create-db
    else
        color '35;1' 'Upgrading databases...'
        alembic upgrade head
    fi
fi

color '35;1' 'Removing .pyc files...'
find . -name \*.pyc -delete

color '35;1' 'Cleaning up...'
apt-get -y purge build-essential
apt-get -y autoremove

mkdir -p /var/lib/inboxapp
chown $SUDO_USER /var/lib/inboxapp

mkdir -p /var/log/inboxapp
chown $SUDO_USER /var/log/inboxapp

git config branch.master.rebase true

color '35;1' 'Done!.'
