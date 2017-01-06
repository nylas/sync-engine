""" Tests for file lock implementation. """

import tempfile

import pytest

from gevent import spawn, sleep

from inbox.util.file import Lock


def lock(block, filename=None):
    if filename is None:
        handle, filename = tempfile.mkstemp()
    return Lock(filename, block=block)


@pytest.fixture
def b_lock():
    """ Blocking lock fixture. """
    return lock(block=True)


@pytest.fixture
def nb_lock():
    """ Non-blocking lock fixture. """
    return lock(block=False)


def grab_lock(l):
    """ Stub fn to grab lock inside a Greenlet. """
    l.acquire()
    print "Got the lock again", l.filename
    l.release()


def test_nb_lock(nb_lock):
    with nb_lock as l:
        filename = l.filename
        with pytest.raises(IOError):
            with lock(block=False, filename=filename):
                pass
    # Should be able to acquire the lock again after the scope ends (also
    # testing that the non-context-manager acquire works).
    l.acquire()
    # Should NOT be able to take the same lock from a Greenlet.
    g = spawn(grab_lock, l)
    g.join()
    assert not g.successful(), "greenlet should throw error"
    l.release()


def test_b_lock(b_lock):
    with b_lock as l:
        # A greenlet should hang forever if it tries to acquire this lock.
        g = spawn(grab_lock, l)
        # Wait long enough that the greenlet ought to be able to finish if
        # it's not blocking, but not long enough to make the test suite hella
        # slow.
        sleep(0.2)
        assert not g.ready(), "greenlet shouldn't be able to grab lock"
