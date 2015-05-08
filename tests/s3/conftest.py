""" Fixtures don't go here; see util/base.py and friends. """
from gevent import monkey
monkey.patch_all(aggressive=False)
