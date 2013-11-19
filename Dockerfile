# DOCKER-VERSION 0.4.0

FROM ubuntu:12.04

MAINTAINER Michael Grinich <mg@inboxapp.com> version: 0.1.0

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
                       git \
                       gcc \
                       python-gevent \
                       python-xapian \
                       libzmq-dev \
                       python-zmq \
                       libmagickwand-dev


# Create default database. Perhaps we should do this at some configuration time
# RUN mysqladmin -u root --password=docker create inboxdb
# RUN mysql -h localhost -u root --password=docker < echo 'create inboxdb'

# TODO add MySQL configuration file
ADD ./deploy/my.cnf /etc/mysql/conf.d/inboxapp.cnf

ADD . /srv/inboxapp
WORKDIR /srv/inboxapp

RUN pip install --upgrade pip
RUN easy_install -U distribute
RUN pip install -r requirements.txt

# Default config file
Add ./config-sample.cfg ./config.cfg'

# Supervisord
ADD    ./deploy/supervisor/supervisord.conf /etc/supervisord.conf
ADD    ./deploy/supervisor/conf.d/nginx.conf /etc/supervisor/conf.d/nginx.conf
ADD    ./deploy/supervisor/conf.d/mysqld.conf /etc/supervisor/conf.d/mysqld.conf
ADD    ./deploy/supervisor/conf.d/inboxapp.conf /etc/supervisor/conf.d/inboxapp.conf


# SSL
ADD ./deploy/certs/inboxapp-combined.crt /etc/ssl/certs/inboxapp-combined.crt
ADD ./deploy/certs/server.key /etc/ssl/private/server.key

# Ngnix
ADD ./deploy/nginx/default.conf /etc/nginx/nginx.conf
ADD ./deploy/nginx/mime.types /etc/nginx/mime.types
RUN bash -c 'rm /etc/nginx/sites-available/default'

RUN apt-get -y purge build-essential
RUN apt-get -y autoremove

# expose 80
# expose 443
volume ["/srv/inboxapp-data"]

# ENTRYPOINT ["/usr/local/bin/supervisord"]
# ENTRYPOINT /bin/bash