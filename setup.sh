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
                   curl


# Install NodeJS
# RUN wget -O - http://nodejs.org/dist/v0.8.26/node-v0.8.26-linux-x64.tar.gz | tar -C /usr/local/ --strip-components=1 -zxv

sudo pip install --upgrade pip

# curl -O http://python-distribute.org/distribute_setup.py && python distribute_setup.py && rm distribute_setup.py distribute-*.tar.gz

pip install --upgrade pip setuptools

pip install -r requirements.txt
pip install -e src

# mysql config
cp ./etc/my.cnf /etc/mysql/conf.d/inboxapp.cnf

# Create default MySQL database and user.
echo "CREATE DATABASE inbox DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_general_ci; GRANT ALL PRIVILEGES ON inbox.* TO inbox@localhost IDENTIFIED BY 'inbox'" | mysql -u root -proot

# Default config file
cp config-sample.cfg config.cfg

apt-get -y purge build-essential
apt-get -y autoremove
