FROM quay.io/inbox/inbox-base:${IMAGE_TAG}

USER admin
ADD ./inbox /srv/inbox

USER root
RUN pip install -e . && rm -f `find . -name *.pyc` && chown -R admin .

USER admin

EXPOSE 5555
