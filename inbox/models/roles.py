from hashlib import sha256
from flanker import mime
from sqlalchemy import Column, Integer, String

from nylas.logging import get_logger
log = get_logger()
from inbox.config import config
from inbox.util.blockstore import save_to_blockstore, get_from_blockstore

# TODO: store AWS credentials in a better way.
STORE_MSG_ON_S3 = config.get('STORE_MESSAGES_ON_S3', None)


class Blob(object):
    """ A blob of data that can be saved to local or remote (S3) disk. """
    size = Column(Integer, default=0)
    data_sha256 = Column(String(64))

    @property
    def data(self):
        if self.size == 0:
            log.warning('Block size is 0')
            return ''
        elif hasattr(self, '_data'):
            # On initial download we temporarily store data in memory
            value = self._data
        else:
            value = get_from_blockstore(self.data_sha256)

        if value is None:
            log.warning("Couldn't find data on S3 for block with hash {}"
                        .format(self.data_sha256))

            from inbox.models.block import Block
            if isinstance(self, Block):
                if self.parts:
                    # This block is an attachment of a message that was
                    # accidentially deleted. We will attempt to fetch the raw
                    # message and parse out the needed attachment.

                    message = self.parts[0].message  # only grab one
                    raw_mime = get_from_blockstore(message.data_sha256)

                    parsed = mime.from_string(raw_mime)
                    if parsed is not None:
                        for mimepart in parsed.walk(
                                with_self=parsed.content_type.is_singlepart()):
                            if mimepart.content_type.is_multipart():
                                continue  # TODO should we store relations?

                            data = mimepart.body

                            # Found it!
                            if sha256(data).hexdigest() == self.data_sha256:
                                log.info('Found subpart with hash {}'.format(
                                    self.data_sha256))
                                save_to_blockstore(self.data_sha256, data)
                                return data

            log.error('No data returned!')
            return value

        assert self.data_sha256 == sha256(value).hexdigest(), \
            "Returned data doesn't match stored hash!"
        return value

    @data.setter
    def data(self, value):
        assert value is not None
        assert type(value) is not unicode

        # Cache value in memory. Otherwise message-parsing incurs a disk or S3
        # roundtrip.
        self._data = value
        self.size = len(value)
        self.data_sha256 = sha256(value).hexdigest()
        assert self.data_sha256

        if len(value) == 0:
            log.warning('Not saving 0-length data blob')
            return

        save_to_blockstore(self.data_sha256, value)
