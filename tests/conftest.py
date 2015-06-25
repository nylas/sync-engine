""" Fixtures don't go here; see util/base.py and friends. """
# Monkeypatch first, to prevent "AttributeError: 'module' object has no
# attribute 'poll'" errors when tests import socket, then monkeypatch.
from gevent import monkey
monkey.patch_all(aggressive=False)
from tests.util.base import *
