FROM debian:wheezy

MAINTAINER inboxapp
RUN apt-get update

RUN apt-get -y install\
    python-software-properties\
    git \
    wget \
    supervisor \
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
    curl \
    tnef && \
    pip install 'setuptools>=5.3'

ADD ./requirements.txt /srv/inbox/

ENV INBOX_srv /srv/inbox

WORKDIR /srv/inbox

RUN pip install -r ./requirements.txt && \
    apt-get -y purge build-essential && \
    apt-get -y autoremove && \
    mkdir -p /var/lib/inboxapp && \
    mkdir -p /var/log/inboxapp

ADD . /srv/inbox

RUN pip install -e .

