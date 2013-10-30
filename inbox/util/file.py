import string
import errno
import os
import fcntl

def safe_filename(filename):
    """ Strip potentially bad characters from a filename so it is safe to
        write to disk.
    """
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    return ''.join(c for c in filename if c in valid_chars)

# http://my.safaribooksonline.com/book/programming/python/0596001673/files/pythoncook-chp-4-sect-16
def splitall(path):
    allparts = []
    while 1:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path: # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])
    return allparts

def mkdirp(path):
    """ An equivalent to mkdir -p. This can go away in Python 3.2;
        just use exists_ok=True.
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

# http://stackoverflow.com/questions/10840533/most-pythonic-way-to-delete-a-file-which-may-not-exist
def remove_file(filename):
    try:
        os.remove(filename)
    except OSError, e:
        if e.errno != errno.ENOENT:
            raise

class Lock:
    """ UNIX-specific exclusive file locks that are released when the process
        ends.

        Based on http://blog.vmfarms.com/2011/03/cross-process-locking-and.html,
        adapted for context managers (the 'with' statement).
    """
    def __init__(self, filename, block=True):
        self.filename = filename
        # This will create it if it does not exist already
        mkdirp(os.path.dirname(filename))
        self.handle = open(filename, 'w')
        if block:
            self.lock_op = fcntl.LOCK_EX
        else:
            self.lock_op = fcntl.LOCK_EX | fcntl.LOCK_NB

    def acquire(self):
        fcntl.flock(self.handle, self.lock_op)

    def release(self):
        fcntl.flock(self.handle, fcntl.LOCK_UN)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self):
        self.release()

    def __del__(self):
        self.handle.close()

def human_readable_filesize(size_bytes, suffixes=None):
    """
    format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
    Note that bytes/KB will be reported in whole numbers but MB and above will have greater precision
    e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
    """
    if size_bytes == 1:
        # because I really hate unnecessary plurals
        return "1 byte"

    if not suffixes:
        suffixes = [('bytes',0),('KB',0),('MB',1),('GB',2),('TB',2), ('PB',2)]

    num = float(size_bytes)
    for suffix, precision in suffixes:
        if num < 1024.0:
            break
        num /= 1024.0

    if precision == 0:
        formatted_size = "%d" % num
    else:
        formatted_size = str(round(num, ndigits=precision))

    return "%s %s" % (formatted_size, suffix)
