import string
import errno
import os
import fcntl

from gevent.coros import BoundedSemaphore


def safe_filename(filename):
    """ Strip filesystem-unfriendly characters from a filename. """
    valid_chars = "-_.() {}{}".format(string.ascii_letters, string.digits)
    return ''.join(c for c in filename if c in valid_chars)


# http://my.safaribooksonline.com/book/programming/python/0596001673/files/pythoncook-chp-4-sect-16
def splitall(path):
    allparts = []
    while 1:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path:  # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])
    return allparts


def mkdirp(path):
    """ An equivalent to mkdir -p.

    This can go away in Python 3.2; just use exists_ok=True.

    Parameters
    ----------
    path : str
        Pathname to create.
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def remove_file(filename):
    """ Delete a file and don't raise an error if it doesn't exist.

    From:
    http://stackoverflow.com/questions/10840533/most-pythonic-way-to-delete-a-file-which-may-not-exist
    """
    try:
        os.remove(filename)
    except OSError, e:
        if e.errno != errno.ENOENT:
            raise


class Lock:
    """ UNIX-specific exclusive file locks (released when the process ends).

    Based on
    http://blog.vmfarms.com/2011/03/cross-process-locking-and.html,
    adapted for context managers (the 'with' statement).

    Modified to be gevent-safe! Locks held by a given Greenlet may not be
    taken by other Greenlets until released, _as long as you only create one
    Lock object per lockfile_. THIS IS VERY IMPORTANT. *Make sure* that you're
    not creating multiple locks on the same file from the same process,
    otherwise you'll bypass the gevent lock!

    Parameters
    ----------
    f : file or str
        File handle or filename to use as the lock.
    block : bool
        Whether to block or throw IOError if the lock is grabbed multiple
        times.
    """
    TIMEOUT = 60

    def __init__(self, f, block=True):
        if isinstance(f, file):
            self.filename = f.name
            self.handle = f if not f.closed else open(f, 'w')
        else:
            self.filename = f
            mkdirp(os.path.dirname(f))
            self.handle = open(f, 'w')
        if block:
            self.lock_op = fcntl.LOCK_EX
        else:
            self.lock_op = fcntl.LOCK_EX | fcntl.LOCK_NB
        self.block = block
        self.gevent_lock = BoundedSemaphore(1)

    def acquire(self):
        got_gevent_lock = self.gevent_lock.acquire(blocking=self.block)
        if not got_gevent_lock:
            raise IOError("cannot acquire gevent lock")
        fcntl.flock(self.handle, self.lock_op)

    def release(self):
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.gevent_lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, type, value, traceback):
        self.release()

    def __del__(self):
        self.handle.close()


def human_readable_filesize(size_bytes, suffixes=None):
    """ Format a size in bytes into a 'human' file size.

    For example, bytes, KB, MB, GB, TB, PB. Note that bytes/KB will be
    reported in whole numbers but MB and above will have greater precision e.g.
    1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc.
    """
    if size_bytes == 1:
        # because I really hate unnecessary plurals
        return "1 byte"

    if not suffixes:
        suffixes = [('bytes', 0), ('KB', 0), ('MB', 1), ('GB', 2), ('TB', 2),
                    ('PB', 2)]

    num = float(size_bytes)
    for suffix, precision in suffixes:
        if num < 1024.0:
            break
        num /= 1024.0

    if precision == 0:
        formatted_size = "{:.0f}".format(num)
    else:
        formatted_size = str(round(num, ndigits=precision))

    return "{} {}".format(formatted_size, suffix)
