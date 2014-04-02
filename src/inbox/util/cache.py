import os, errno
import msgpack

from .file import safe_filename, mkdirp, splitall

# A quick hack of a key-value cache of arbitrary data structures. Stores on disk.
# XXX TODO: before prod deploy, make this configurable.
from inbox.server.config import config

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
    packed = msgpack.Packer(encoding=PACK_ENCODING).pack(val)
    with open(path, 'w') as f:
        f.write(packed)


def _unless_dne(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except IOError as e:
        if e.errno == errno.ENOENT:
            return None
        else: raise

def get_cache(key):
    return _unless_dne(lambda: _load_cache(_path_from_key(key)))


def _load_cache(path):
    unpacker = msgpack.Unpacker()
    with open(path, 'r') as f:
        unpacker.feed(f.read())
    return unpacker.unpack()


def rm_cache(key):
    _unless_dne(os.remove, _path_from_key(key))
