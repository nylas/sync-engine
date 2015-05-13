import os
from hashlib import sha256

from sqlalchemy import Column, Integer, String

from inbox.config import config
from inbox.log import get_logger
log = get_logger()

# TODO: store AWS credentials in a better way.
STORE_MSG_ON_S3 = config.get('STORE_MESSAGES_ON_S3', None)

if STORE_MSG_ON_S3:
    from boto.s3.connection import S3Connection
    from boto.s3.key import Key
else:
    from inbox.util.file import mkdirp

    _data_file_directory = \
        lambda h: os.path.join(config.get_required('MSG_PARTS_DIRECTORY'),
                               h[0], h[1], h[2], h[3], h[4], h[5])

    _data_file_path = lambda h: os.path.join(_data_file_directory(h), h)


class Blob(object):
    """ A blob of data that can be saved to local or remote (S3) disk. """

    size = Column(Integer, default=0)
    data_sha256 = Column(String(64))

    @property
    def data(self):
        if self.size == 0:
            log.warning('Block size is 0')
            # Placeholder for "empty bytes". If this doesn't work as intended,
            # it will trigger the hash assertion later.
            value = ""
        elif hasattr(self, '_data'):
            # On initial download we temporarily store data in memory
            value = self._data
        elif STORE_MSG_ON_S3:
            value = self._get_from_s3()
        else:
            value = self._get_from_disk()

        if value is None:
            log.error('No data returned!')
            return value

        assert self.data_sha256 == sha256(value).hexdigest(), \
            "Returned data doesn't match stored hash!"
        return value

    @data.setter
    def data(self, value):
        assert value is not None, \
            "Blob can't have NoneType data (can be zero-length, though!)"
        assert type(value) is not unicode, 'Blob bytes must be encoded'

        # Cache value in memory. Otherwise message-parsing incurs a disk or S3
        # roundtrip.
        self._data = value
        self.size = len(value)
        self.data_sha256 = sha256(value).hexdigest()
        assert self.data_sha256

        if self.size > 0:
            if STORE_MSG_ON_S3:
                self._save_to_s3(value)
            else:
                self._save_to_disk(value)
        else:
            log.warning('Not saving 0-length {1} {0}'.format(
                self.id, self.__class__.__name__))

    def _save_to_s3(self, data):
        assert 'AWS_ACCESS_KEY_ID' in config, 'Need AWS key!'
        assert 'AWS_SECRET_ACCESS_KEY' in config, 'Need AWS secret!'
        assert 'MESSAGE_STORE_BUCKET_NAME' in config, \
            'Need bucket name to store message data!'

        # Boto pools connections at the class level
        conn = S3Connection(config.get('AWS_ACCESS_KEY_ID'),
                            config.get('AWS_SECRET_ACCESS_KEY'))
        bucket = conn.get_bucket(config.get('MESSAGE_STORE_BUCKET_NAME'),
                                 validate=False)

        # See if it already exists; if so, don't recreate.
        key = bucket.get_key(self.data_sha256)
        if key:
            return

        key = Key(bucket)
        key.key = self.data_sha256
        key.set_contents_from_string(data)

    def _get_from_s3(self):
        if not self.data_sha256:
            return None

        conn = S3Connection(config.get('AWS_ACCESS_KEY_ID'),
                            config.get('AWS_SECRET_ACCESS_KEY'))
        bucket = conn.get_bucket(config.get('MESSAGE_STORE_BUCKET_NAME'),
                                 validate=False)

        key = bucket.get_key(self.data_sha256)

        if not key:
            log.error('No key with name: {} returned!'.
                      format(self.data_sha256))
            return

        return key.get_contents_as_string()

    def _save_to_disk(self, data):
        directory = _data_file_directory(self.data_sha256)
        mkdirp(directory)

        with open(_data_file_path(self.data_sha256), 'wb') as f:
            f.write(data)

    def _get_from_disk(self):
        if not self.data_sha256:
            return None

        try:
            with open(_data_file_path(self.data_sha256), 'rb') as f:
                return f.read()
        except IOError:
            log.error('No file with name: {}!'.format(self.data_sha256))
            return
