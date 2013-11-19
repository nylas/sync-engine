# DOCKER-VERSION 0.4.0

FROM ubuntu:12.04

MAINTAINER Michael Grinich <mg@inboxapp.com> version: 0.1.0

RUN apt-get -y install python-software-properties

RUN echo 'deb http://us.archive.ubuntu.com/ubuntu/ precise universe' >> /etc/apt/sources.list
RUN add-apt-repository -y ppa:nginx/stable
RUN apt-get -y update
RUN apt-get -y upgrade --force-yes

RUN apt-get -y install nginx supervisor mysql-server mysql-client python python-dev python-pip build-essential libmysqlclient-dev git gcc python-gevent python-xapian


# Preconfigure MySQL passwords
run   echo "mysql-server mysql-server/root_password password docker" | debconf-set-selections
run   echo "mysql-server mysql-server/root_password_again password docker" | debconf-set-selections


# Create default database. Perhaps we should do this at some configuration time
# RUN mysqladmin -u root --password=hunter2 create inbox-db
# TODO MySQL configuration file

RUN pip install --upgrade pip
RUN easy_install -U distribute

ADD . /srv/inboxapp
WORKDIR /srv/inboxapp
RUN pip install -r requirements.txt

# RUN bash -c 'cp config-sample config.cfg'


# Supervisord
ADD    ./deploy/supervisor/supervisord.conf /etc/supervisord.conf
ADD    ./deploy/supervisor/conf.d/nginx.conf /etc/supervisor/conf.d/nginx.conf
ADD    ./deploy/supervisor/conf.d/mysqld.conf /etc/supervisor/conf.d/mysqld.conf
ADD    ./deploy/supervisor/conf.d/inboxapp.conf /etc/supervisor/conf.d/inboxapp.conf

# Ngnix
ADD ./deploy/nginx/default.conf /etc/nginx/sites-enabled/default
ADD ./deploy/nginx/mime.types /etc/nginx/sites-enabled/mime.types

RUN apt-get -y purge build-essential
RUN apt-get -y autoremove

expose 80
expose 443
volume ["/srv/inboxapp-data"]
ENTRYPOINT ["/usr/local/bin/supervisord", "-n"]
