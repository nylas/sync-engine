# -*- coding: utf-8 -*-
def test_base36_validation():
    from inbox.events.util import valid_base36
    assert valid_base36("1234zerzerzedsfsd") is True
    assert valid_base36("zerzerzedsfsd") is True
    assert valid_base36("é(§è!è§('") is False
    assert valid_base36("_°987643") is False


def test_event_organizer_parsing():
    from inbox.models.event import Event
    e = Event()
    e.owner = 'Jean Lecanuet <jean.lecanuet@orange.fr>'
    assert e.organizer_email == 'jean.lecanuet@orange.fr'

    e.owner = u'Pierre Mendès-France <pierre-mendes.france@orange.fr >'
    assert e.organizer_email == 'pierre-mendes.france@orange.fr'

    e.owner = u'Pierre Messmer <   pierre.messmer@orange.fr >'
    assert e.organizer_email == 'pierre.messmer@orange.fr'


def test_removed_participants():
    from inbox.events.util import removed_participants
    helena = {'email': 'helena@nylas.com', 'name': 'Helena Handbasket'}
    ben = {'email': 'ben@nylas.com', 'name': 'Ben Handbasket'}
    paul = {'email': 'paul@nylas.com', 'name': 'Paul Hochon'}

    assert removed_participants([], []) == []
    assert removed_participants([helena], [ben]) == [helena]
    assert removed_participants([helena, ben], [helena]) == [ben]
    assert removed_participants([helena, ben], [paul, helena]) == [ben]
    assert len(removed_participants([helena, ben, paul], [helena])) == 2
    assert ben in removed_participants([helena, ben, paul], [helena])
    assert paul in removed_participants([helena, ben, paul], [helena])
