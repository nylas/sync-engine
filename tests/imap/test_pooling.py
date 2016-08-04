import imaplib
import socket

import gevent
import pytest
import mock
from backports import ssl

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


@pytest.mark.parametrize("error_class,expect_logout_called", [
    (imaplib.IMAP4.error, True),
    (imaplib.IMAP4.abort, False),
    (socket.error, False),
    (socket.timeout, False),
    (ssl.SSLError, False),
    (ssl.CertificateError, False),
])
def test_imap_and_network_errors(error_class, expect_logout_called):
    pool = TestableConnectionPool(1, num_connections=3, readonly=True)
    with pytest.raises(error_class):
        with pool.get() as conn:
            raise error_class
    assert pool._queue.full()
    # Check that the connection wasn't returned to the pool
    while not pool._queue.empty():
        item = pool._queue.get()
        assert item is None
    assert conn.logout.called is expect_logout_called


def test_connection_retained_on_other_errors():
    pool = TestableConnectionPool(1, num_connections=3, readonly=True)
    with pytest.raises(ValueError):
        with pool.get() as conn:
            raise ValueError
    assert conn in pool._queue
    assert not conn.logout.called
