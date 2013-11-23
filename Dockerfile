# DOCKER-VERSION 0.4.0

FROM ubuntu:12.04

MAINTAINER Michael Grinich <mg@inboxapp.com> version: 0.1.0

# this forces dpkg not to call sync() after package extraction and speeds up install
# RUN echo "force-unsafe-io" > /etc/dpkg/dpkg.cfg.d/02apt-speedup
# we don't need and apt cache in a container
# RUN echo "Acquire::http {No-Cache=True;};" > /etc/apt/apt.conf.d/no-cache

RUN apt-get -y install python-software-properties

RUN echo 'deb http://us.archive.ubuntu.com/ubuntu/ precise universe' >> /etc/apt/sources.list
RUN add-apt-repository -y ppa:nginx/stable
RUN apt-get -y update
RUN apt-get -y upgrade --force-yes

# Preconfigure MySQL root password
RUN echo "mysql-server mysql-server/root_password password docker" | debconf-set-selections
RUN echo "mysql-server mysql-server/root_password_again password docker" | debconf-set-selections

# Dependencies
RUN apt-get -y install git \
                       nginx \
                       supervisor \
                       mysql-server \
                       mysql-client \
                       python \
                       python-dev \
                       python-pip \
                       build-essential \
                       libmysqlclient-dev \
                       gcc \
                       python-gevent \
                       python-xapian \
                       libzmq-dev \
                       python-zmq \
                       python-lxml \
                       libmagickwand-dev \
                       tmux


# Install requirements from PyPI and GitHub
RUN pip install --upgrade pip
RUN easy_install -U distribute

RUN pip install argparse==1.2.1 \
                beautifulsoup4==4.1.3 \
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
                gunicorn==17.5 \
                colorlog==1.8 \
                MySQL-python==1.2.4 \
                requests==2.0.0 \
                Fabric==1.7.0 \
                supervisor==3.0 \
                chardet==2.1.1 \
                PIL==1.1.7 \
                Wand==0.3.5 \
                setproctitle==1.1.7 \
                Cython==0.19.1 \
                zerorpc==0.4.3 \
                gdata==2.0.18 \
                python-dateutil==2.1 \
                flanker==0.3.2 \
                git+https://github.com/zeromq/pyzmq.git@v13.1.0#egg=zmq \
                git+https://github.com/inboxapp/imapclient.git#egg=imapclient \
                git+https://github.com/inboxapp/bleach.git#egg=bleach \
                git+https://github.com/inboxapp/iconv.git#egg=iconv


# MySQL
ADD ./deploy/my.cnf /etc/mysql/conf.d/inboxapp.cnf

# Create default MySQL database. Perhaps we should do this at some configuration time
RUN /usr/sbin/mysqld & sleep 5 ; echo "CREATE DATABASE inboxdb DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_general_ci" | mysql -u root --password=docker

ADD . /srv/inboxapp
WORKDIR /srv/inboxapp

# Default config file
RUN cp config-sample.cfg config.cfg

RUN apt-get -y purge build-essential
RUN apt-get -y autoremove

volume ["/srv/inboxapp-data"]

# The server listens on port 5000 for now
EXPOSE 5000

ENTRYPOINT /usr/bin/mysqld_safe & /bin/bash
