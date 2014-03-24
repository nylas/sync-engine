#!/bin/sh
set -e

apt-get update
apt-get -y install python-software-properties

# Preconfigure MySQL root password
echo "mysql-server mysql-server/root_password password root" | debconf-set-selections
echo "mysql-server mysql-server/root_password_again password root" | debconf-set-selections

# Dependencies
apt-get -y install git \
                   wget \
                   supervisor \
                   mysql-server \
                   mysql-client \
                   redis-server \
                   python \
                   python-dev \
                   python-pip \
                   python-setuptools \
                   build-essential \
                   libmysqlclient-dev \
                   gcc \
                   python-gevent \
                   python-xapian \
                   libzmq-dev \
                   python-zmq \
                   libxml2-dev \
                   libxslt-dev \
                   lib32z1-dev \
                   python-lxml \
                   libmagickwand-dev \
                   tmux \
                   curl \
                   stunnel4

pip install --upgrade setuptools

pip install -r requirements.txt
pip install -e src
if [ -d "../inbox-eas" ];
    pip install -e ../inbox-eas
fi
if [ -d "../inbox-util" ];
    pip install -e ../inbox-util
fi

echo '[InboxApp] Finished installing dependencies.'

# mysql config
cp ./etc/my.cnf /etc/mysql/conf.d/inboxapp.cnf

mysqld_safe &
sleep 10

python tools/create_db.py

apt-get -y purge build-essential
apt-get -y autoremove
