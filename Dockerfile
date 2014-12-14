###############
# inbox/inbox #
###############

FROM debian:wheezy

MAINTAINER inboxapp
RUN apt-get -q update && \
    DEBIAN_FRONTEND=noninteractive apt-get -qy install \
        anacron \
        build-essential \
        cron \
        curl \
        g++ \
        gcc \
        git \
        lib32z1-dev \
        libffi-dev \
        libmysqlclient-dev \
        libxml2-dev \
        libxslt-dev \
        libzmq-dev \
        mysql-client \
        net-tools \
        procps \
        python \
        python-dev \
        python-lxml \
        python-pip \
        python-setuptools \
        python-software-properties\
        runit \
        sudo \
        supervisor \
        tnef \
        wget \
    && \
    pip install 'setuptools>=5.3' subprocess32 tox

RUN useradd -ms /bin/sh admin && \
    install -d -m0775 -o root -g admin /srv/inbox
WORKDIR /srv/inbox

ADD requirements.txt /srv/inbox/requirements.txt
RUN pip install -r /srv/inbox/requirements.txt

# XXX: This is to work around some problem with installing the deps from tox.ini
RUN pip install \
        pytest \
        pytest-flask \
        pytest-instafail \
        pytest-timeout \
        pytest-xdist \
        requests

RUN install -d -m0775 -o root -g admin /etc/inboxapp && \
    install -d -m0775 -o root -g admin /etc/mysql/conf.d && \
    install -d -m0775 -o root -g admin /run/inboxapp && \
    install -d -m0775 -o root -g admin /run/supervisor && \
    ln -s /srv/inbox/docker /srv/docker && \
    chown -R admin /usr/local/lib/python2.7

#@DYNAMIC base
ADD . /srv/inbox
RUN /srv/inbox/docker/postinstall-src /srv/inbox && \
    install -m0755 docker/inbox-cron-hourly /etc/cron.hourly/inbox-cron-hourly && \
    install -m0755 docker/inbox-cron-daily /etc/cron.daily/inbox-cron-daily && \
    install -m0755 docker/inbox-cron-weekly /etc/cron.weekly/inbox-cron-weekly && \
    install -m0755 docker/inbox-cron-monthly /etc/cron.monthly/inbox-cron-monthly

ENTRYPOINT ["/srv/docker/entrypoint"]
ENV INBOX_CFG_PATH /etc/inboxapp/secrets.yml:/etc/inboxapp/config.json:/run/inboxapp/secrets.yml:/run/inboxapp/config.json
EXPOSE 5555

# Permissions for some of these are set in docker/entrypoint.
VOLUME ["/etc/inboxapp", "/var/lib/inboxapp", "/var/log/inboxapp", "/var/log/supervisor"]
