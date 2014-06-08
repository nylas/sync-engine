import os, errno
import msgpack

from .file import safe_filename, mkdirp, splitall

# A quick hack of a key-value cache of arbitrary data structures. Stores on disk.
# XXX TODO: before prod deploy, make this configurable.
from inbox.config import config
from inbox.log import get_logger
log = get_logger()


PACK_ENCODING='utf-8'


def _path_from_key(key):
    parts = [safe_filename(part) for part in splitall(key)]
    cache_dir = config.get('CACHE_BASEDIR', None)
    assert cache_dir, "Need directory to store cache! Set CACHE_BASEDIR in config.cfg"
    return os.path.join(cache_dir, *parts)


def set_cache(key, val):
    path = _path_from_key(key)
    dirname = os.path.dirname(path)
    mkdirp(dirname)
    log.info("Saving cache to {0}".format(dirname))
    with open(path, 'w') as f:
        msgpack.pack(val, f)


def _unless_dne(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except IOError as e:
        if e.errno == errno.ENOENT:
            return None
        else: raise


def get_cache(key):
    cache_path = _path_from_key(key)
    log.info("Loading cache to {0}".format(cache_path))
    return _unless_dne(lambda: _load_cache(cache_path))


def _load_cache(path):
    with open(path, 'r') as f:
        d = msgpack.unpack(f)
    return d


def rm_cache(key):
    _unless_dne(os.remove, _path_from_key(key))
