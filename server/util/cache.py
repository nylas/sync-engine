import os, errno
import cPickle as pickle
import logging as log

from server.util import safe_filename, mkdirp

# A quick hack of a key-value cache of arbitrary data structures. Stores on disk.
CACHE_BASEDIR='cache'

def _path_from_key(key):
    return os.path.join(CACHE_BASEDIR, safe_filename(key))

def set_cache(key, val):
    mkdirp(CACHE_BASEDIR)
    with open(_path_from_key(key), 'w') as f:
        pickle.dump(val, f)

def _unless_dne(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except IOError as e:
        log.warning("Cache file does not exist.")
        if e.errno == errno.ENOENT:
            return None
        else: raise

def get_cache(key):
    return _unless_dne(lambda: pickle.load(file(_path_from_key(key))))

def rm_cache(key):
    _unless_dne(os.remove, _path_from_key(key))
