import os, errno
import cPickle as pickle

from .file import safe_filename, mkdirp, splitall

# A quick hack of a key-value cache of arbitrary data structures. Stores on disk.
# XXX TODO: before prod deploy, make this configurable.
CACHE_BASEDIR='cache'

def _path_from_key(key):
    parts = [safe_filename(part) for part in splitall(key)]
    return os.path.join(CACHE_BASEDIR, *parts)

def set_cache(key, val):
    path = _path_from_key(key)
    dirname = os.path.dirname(path)
    mkdirp(dirname)
    with open(path, 'w') as f:
        pickle.dump(val, f)

def _unless_dne(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except IOError as e:
        if e.errno == errno.ENOENT:
            return None
        else: raise

def get_cache(key):
    return _unless_dne(lambda: pickle.load(file(_path_from_key(key))))

def rm_cache(key):
    _unless_dne(os.remove, _path_from_key(key))
