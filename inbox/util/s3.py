from contextlib import contextmanager
from gevent.queue import LifoQueue
from boto.s3.connection import S3Connection
from boto.s3.key import Key
from inbox.config import config


def save(data, data_sha256, use_pool=True):
    # STOPSHIP(emfree): handle any errors
    if use_pool:
        with pool().get() as bucket:
            _save(bucket, data, data_sha256)
    else:
        bucket = _get_bucket()
        _save(bucket, data, data_sha256)


def load(data_sha256, use_pool=True):
    if use_pool:
        with pool().get() as bucket:
            data_obj = bucket.get_key(data_sha256)
            assert data_obj, "No data returned!"
            return data_obj.get_contents_as_string()
    else:
        bucket = _get_bucket()
        data_obj = bucket.get_key(data_sha256)
        assert data_obj, "No data returned!"
        return data_obj.get_contents_as_string()


def _save(bucket, data, data_sha256):
    # See if data object already exists on S3 and has the same hash
    data_obj = bucket.get_key(data_sha256)
    if data_obj:
        assert data_obj.get_metadata('data_sha256') == data_sha256, \
            "Block hash doesn't match what we previously stored on s3!"
        return
    # If it doesn't already exist, save it.
    data_obj = Key(bucket)
    data_obj.set_metadata('data_sha256', data_sha256)
    data_obj.key = data_sha256
    data_obj.set_contents_from_string(data)


def _get_bucket():
    conn = S3Connection(config.get_required('AWS_ACCESS_KEY_ID'),
                        config.get_required('AWS_SECRET_ACCESS_KEY'))
    return conn.get_bucket(config.get_required('MESSAGE_STORE_BUCKET_NAME'))


class S3ConnectionPool(object):
    # TODO(emfree): we should maybe think about adapting geventconnpool for
    # this.
    def __init__(self, pool_size=22):
        self._stack = LifoQueue()
        for _ in range(pool_size):
            bucket = _get_bucket()
            self._stack.put(bucket)

    @contextmanager
    def get(self):
        bucket = self._stack.get()
        try:
            yield bucket
        finally:
            self._stack.put(bucket)


__pool = None


def pool():
    global __pool
    if __pool is None:
        __pool = S3ConnectionPool()
        return __pool
