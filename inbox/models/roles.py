import os
from hashlib import sha256

import nacl.secret
import nacl.utils
from sqlalchemy import Column, Integer, String

from inbox.config import config
from inbox.log import get_logger
log = get_logger()
from inbox.models.util import EncryptionScheme

STORE_MSG_ON_S3 = config.get('STORE_MESSAGES_ON_S3', None)
# Enable by defining these in your config
# "STORE_MESSAGES_ON_S3" : false,
# "AWS_ACCESS_KEY_ID": "<YOUR_AWS_ACCESS_KEY>"
# "AWS_SECRET_ACCESS_KEY": "<YOUR_AWS_ACCESS_KEY>",
# "MESSAGE_STORE_BUCKET_NAME": "<YOUR_AWS_ACCESS_KEY>",

if STORE_MSG_ON_S3:
    from boto.s3.connection import S3Connection
    from boto.s3.key import Key
else:
    from inbox.util.file import mkdirp, remove_file


class Blob(object):
    """ A blob of data that can be saved to local or remote (S3) disk. """

    size = Column(Integer, default=0)
    data_sha256 = Column(String(64))

    encryption_scheme = Column(Integer, server_default='0', nullable=False)

    @property
    def data(self):
        encrypted = True
        if self.size == 0:
            log.warning('block size is 0')
            # NOTE: This is a placeholder for "empty bytes". If this doesn't
            # work as intended, it will trigger the hash assertion later.
            value = ""
            encrypted = False
        elif hasattr(self, '_data'):
            # On initial download we temporarily store data unencrypted
            # in memory
            value = self._data
            encrypted = False
        elif STORE_MSG_ON_S3:
            value = self._get_from_s3()
        else:
            value = self._get_from_disk()

        if value is None:
            log.error("Couldn't find data!")
            return value

        # Decrypt if reqd.
        if encrypted and self.encryption_scheme == \
                EncryptionScheme.SECRETBOX_WITH_STATIC_KEY:
            value = nacl.secret.SecretBox(
                key=config.get_required('BLOCK_ENCRYPTION_KEY'),
                encoder=nacl.encoding.HexEncoder
            ).decrypt(
                value,
                encoder=nacl.encoding.HexEncoder)

        assert self.data_sha256 == sha256(value).hexdigest(), \
            "Returned data doesn't match stored hash!"
        return value

    @data.setter
    def data(self, value):
        # Cache value in memory unencrypted. Otherwise message-parsing incurs
        # a disk or S3 roundtrip.
        self._data = value

        assert value is not None, \
            "Blob can't have NoneType data (can be zero-length, though!)"
        assert type(value) is not unicode, 'Blob bytes must be encoded'

        self.size = len(value)
        self.data_sha256 = sha256(value).hexdigest()

        # Encrypt before saving
        self.encryption_scheme = EncryptionScheme.SECRETBOX_WITH_STATIC_KEY

        encrypted_value = nacl.secret.SecretBox(
            key=config.get_required('BLOCK_ENCRYPTION_KEY'),
            encoder=nacl.encoding.HexEncoder
        ).encrypt(
            plaintext=value,
            nonce=self.data_sha256[:nacl.secret.SecretBox.NONCE_SIZE],
            encoder=nacl.encoding.HexEncoder)

        if self.size > 0:
            if STORE_MSG_ON_S3:
                self._save_to_s3(encrypted_value)
            else:
                self._save_to_disk(encrypted_value)
        else:
            log.warning('Not saving 0-length {1} {0}'.format(
                self.id, self.__class__.__name__))

    @data.deleter
    def data(self):
        if self.size == 0:
            return
        if STORE_MSG_ON_S3:
            self._delete_from_s3()
        else:
            self._delete_from_disk()
        self.size = None
        self.data_sha256 = None

    def _save_to_s3(self, data):
        assert len(data) > 0, 'Need data to save!'

        access_key = config.get_required('AWS_ACCESS_KEY_ID')
        secret_key = config.get_required('AWS_SECRET_ACCESS_KEY')
        bucket_name = config.get_required('MESSAGE_STORE_BUCKET_NAME')

        # Boto pools connections at the class level
        conn = S3Connection(access_key, secret_key)
        bucket = conn.get_bucket(bucket_name, validate=False)

        # See if it already exists and has the same hash
        data_obj = bucket.get_key(self.data_sha256)
        if data_obj:
            assert data_obj.get_metadata('data_sha256') == self.data_sha256, \
                "Block hash doesn't match what we previously stored on s3!"
            return

        data_obj = Key(bucket)
        # if metadata:
        #     assert type(metadata) is dict
        #     for k, v in metadata.iteritems():
        #         data_obj.set_metadata(k, v)
        data_obj.set_metadata('data_sha256', self.data_sha256)
        # data_obj.content_type = self.content_type  # Experimental
        data_obj.key = self.data_sha256
        # log.info("Writing data to S3 with hash {0}".format(self.data_sha256))
        # def progress(done, total):
        #     log.info("%.2f%% done" % (done/total * 100) )
        # data_obj.set_contents_from_string(data, cb=progress)
        data_obj.set_contents_from_string(data)

    def _get_from_s3(self):
        assert self.data_sha256, "Can't get data with no hash!"

        access_key = config.get_required('AWS_ACCESS_KEY_ID')
        secret_key = config.get_required('AWS_SECRET_ACCESS_KEY')
        bucket_name = config.get_required('MESSAGE_STORE_BUCKET_NAME')

        # Boto pools connections at the class level
        conn = S3Connection(access_key, secret_key)
        bucket = conn.get_bucket(bucket_name, validate=False)

        data_obj = bucket.get_key(self.data_sha256)
        assert data_obj, 'No data returned!'

        return data_obj.get_contents_as_string()

    def _delete_from_s3(self):
        # TODO
        pass

    # Helpers
    @property
    def _data_file_directory(self):
        assert self.data_sha256
        # Nest it 6 items deep so we don't have folders with too many files.
        h = self.data_sha256
        root = config.get_required('MSG_PARTS_DIRECTORY')
        return os.path.join(root,
                            h[0], h[1], h[2], h[3], h[4], h[5])

    @property
    def _data_file_path(self):
        return os.path.join(self._data_file_directory, self.data_sha256)

    def _save_to_disk(self, data):
        mkdirp(self._data_file_directory)
        with open(self._data_file_path, 'wb') as f:
            f.write(data)

    def _get_from_disk(self):
        try:
            with open(self._data_file_path, 'rb') as f:
                return f.read()
        except Exception:
            log.error('No data for hash {0}'.format(self.data_sha256))
            # XXX should this instead be empty bytes?
            return None

    def _delete_from_disk(self):
        remove_file(self._data_file_path)
