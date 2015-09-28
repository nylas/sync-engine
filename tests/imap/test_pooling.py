import imaplib
import gevent
import pytest
import mock
from inbox.crispin import CrispinConnectionPool


class TestableConnectionPool(CrispinConnectionPool):
    def _set_account_info(self):
        pass

    def _new_connection(self):
        return mock.Mock()


def test_pool():
    pool = TestableConnectionPool(1, num_connections=3, readonly=True)
    with pool.get() as conn:
        pass
    assert pool._queue.full()
    assert conn in pool._queue


def test_block_on_depleted_pool():
    pool = TestableConnectionPool(1, num_connections=1, readonly=True)
    # Test that getting a connection when the pool is empty blocks
    with pytest.raises(gevent.hub.LoopExit):
        with pool.get():
            with pool.get():
                pass


def test_connection_discarded_on_imap_errors():
    pool = TestableConnectionPool(1, num_connections=3, readonly=True)
    with pytest.raises(imaplib.IMAP4.error):
        with pool.get() as conn:
            raise imaplib.IMAP4.error
    assert pool._queue.full()
    # Check that the connection wasn't returned to the pool
    while not pool._queue.empty():
        item = pool._queue.get()
        assert item is None
    assert conn.logout.called


def test_connection_retained_on_other_errors():
    pool = TestableConnectionPool(1, num_connections=3, readonly=True)
    with pytest.raises(ValueError):
        with pool.get() as conn:
            raise ValueError
    assert conn in pool._queue
    assert conn.logout.called == False
