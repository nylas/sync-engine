# -*- coding: utf-8 -*-

from inbox.events.util import valid_base36


def test_base36_validation():
    assert valid_base36("1234zerzerzedsfsd") is True
    assert valid_base36("zerzerzedsfsd") is True
    assert valid_base36("é(§è!è§('") is False
    assert valid_base36("_°987643") is False
