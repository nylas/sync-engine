#!/bin/sh

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
                   python-lxml \
                   libmagickwand-dev \
                   tmux \
                   curl

# Install requirements from PyPI and GitHub
pip install --upgrade pip setuptools

curl -O http://python-distribute.org/distribute_setup.py && python distribute_setup.py&& rm distribute_setup.py distribute-*.tar.gz

pip install argparse==1.2.1 \
            beautifulsoup4==4.3.2 \
            httplib2==0.8 \
            pytest==2.3.4 \
            tornado==3.0.1 \
            wsgiref==0.1.2 \
            futures==2.1.3 \
            jsonrpclib==0.1.3 \
            SQLAlchemy==0.8.3 \
            pymongo==2.5.2  \
            dnspython==1.11.0 \
            boto==2.10.0 \
            ipython==1.0.0 \
            Flask==0.10.1 \
            gevent-socketio==0.3.5-rc2 \
            geventconnpool==0.2 \
            gunicorn==17.5 \
            colorlog==1.8 \
            MySQL-python==1.2.4 \
            requests==2.0.0 \
            Fabric==1.7.0 \
            supervisor==3.0 \
            chardet==2.1.1 \
            Wand==0.3.5 \
            setproctitle==1.1.8 \
            Cython==0.19.1 \
            zerorpc==0.4.3 \
            gdata==2.0.18 \
            python-dateutil==2.2 \
            flanker==0.3.3

pip install git+https://github.com/zeromq/pyzmq.git@v13.1.0#egg=zmq
pip install git+https://github.com/inboxapp/imapclient.git#egg=imapclient
pip install git+https://github.com/inboxapp/bleach.git#egg=bleach

pip install  http://effbot.org/media/downloads/Imaging-1.1.7.tar.gz#egg=PIL

pip install -e src

# Install NodeJS for web client (eventually)
# wget -O - http://nodejs.org/dist/v0.8.26/node-v0.8.26-linux-x64.tar.gz | tar -C /usr/local/ --strip-components=1 -zxv

# mysql config
cp ./etc/my.cnf /etc/mysql/conf.d/inboxapp.cnf

# Create default MySQL database and user.
echo "CREATE DATABASE inbox DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_general_ci; GRANT ALL PRIVILEGES ON inbox.* TO inbox@localhost IDENTIFIED BY 'inbox'" | mysql -u root -proot

# Default config file
cp config-sample.cfg config.cfg

apt-get -y purge build-essential
apt-get -y autoremove
