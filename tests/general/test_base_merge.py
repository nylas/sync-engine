import pytest

from inbox.util.misc import merge_attr
from inbox.util.misc import MergeError


class C:
    def __init__(self, attr):
        self.attr = attr


def merge(base, remote, dest):
    a = C(base)
    b = C(remote)
    c = C(dest)
    merge_attr(a, b, c, 'attr')
    return c.attr


def test_no_change():
    base = {'k': 'v'}
    remote = {'k': 'v'}
    dest = {'k': 'v'}
    dest = merge(base, remote, dest)
    assert 'k' in dest and dest['k'] == 'v'


def test_nones():
    base = None
    remote = {'k': 'v'}
    dest = None
    dest = merge(base, remote, dest)
    assert 'k' in dest and dest['k'] == 'v'

    base = {'k': 'v'}
    remote = None
    dest = None
    dest = merge(base, remote, dest)
    assert dest is None or dest == {}

    base = {'k': 'v'}
    remote = None
    dest = {'k': 'v'}
    dest = merge(base, remote, dest)
    assert dest is None or dest == {}

    base = None
    remote = {'k': 'v'}
    dest = {'k': 'v'}
    dest = merge(base, remote, dest)
    assert 'k' in dest and dest['k'] == 'v'


def test_update_keys():
    base = {'k': 'v'}
    remote = {'k': 'v2'}
    dest = {'k': 'v'}
    dest = merge(base, remote, dest)
    assert 'k' in dest and dest['k'] == 'v2'

    with pytest.raises(MergeError):
        base = {}
        remote = {'k': 'v'}
        dest = {'k': 'v2'}
        dest = merge(base, remote, dest)

    base = {'k': 'v'}
    remote = {'k2': 'v2', 'k3': 'v3'}
    dest = {'k': 'v'}
    dest = merge(base, remote, dest)
    assert 'k2' in dest and dest['k2'] == 'v2'
    assert 'k3' in dest and dest['k3'] == 'v3'
    assert 'k' not in dest

    base = {'k': 'v'}
    remote = {'k': 'v2', 'k2': 'v2', 'k3': 'v3'}
    dest = {'k': 'v'}
    dest = merge(base, remote, dest)
    assert 'k' in dest and dest['k'] == 'v2'
    assert 'k2' in dest and dest['k2'] == 'v2'
    assert 'k3' in dest and dest['k3'] == 'v3'
