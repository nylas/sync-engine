FROM quay.io/inbox/inbox-base

USER admin
ADD . /srv/inbox

USER root
RUN pip install -e .

USER admin

