# Basic tests for events merging.
from inbox.models.event import Event


def fake_event():
    return Event(title="The fifth element",
                 participants=[{"name": "Ronald Zubar",
                                "email": "ronald@example.com",
                                "status": "noreply",
                                "notes": "required"}])


def fake_event2():
    return Event(title="The fifth element",
                 participants=[{"name": "Ronald Zubar",
                                "email": "ronald@example.com",
                                "status": "noreply",
                                "notes": "required"},
                               {"name": "Ronald McDonald",
                                "email": "ronald@mcdonalds.com",
                                "status": "noreply",
                                "notes": "required"}])


def test_overwrite():
    ev = fake_event()
    ev2 = fake_event()
    ev2.participants[0]["status"] = "yes"

    merged_participants = ev._partial_participants_merge(ev2)
    assert merged_participants[0]["status"] == "yes"


def test_name_merging():
    # Test that we merge correctly emails and names.
    ev = fake_event()
    ev2 = fake_event()

    # Office365 sets the name to the email address when it's
    # not available.
    ev.participants[0]["name"] = "ronald@example.com"
    ev2.participants[0]["status"] = "yes"
    merged_participants = ev._partial_participants_merge(ev2)

    assert len(merged_participants) == 1
    assert merged_participants[0]["status"] == "yes"
    assert merged_participants[0]["name"] == "Ronald Zubar"


def test_name_conflicts():
    # Test that we handle participants having the same name correctly.
    ev = fake_event()
    ev2 = fake_event()

    # Office365 sets the name to the email address when it's
    # not available.
    ev2.participants[0]["email"] = None
    ev2.participants[0]["status"] = "yes"
    merged_participants = ev._partial_participants_merge(ev2)

    assert len(merged_participants) == 2
    for participant in merged_participants:
        if participant["email"] is None:
            assert participant["status"] == "yes"
        else:
            assert participant["name"] == "Ronald Zubar"


def test_no_unrelated_overwrites():
    # Test that we're not overwriting participants who haven't been
    # updated.
    ev = fake_event2()
    ev2 = fake_event()

    ev2.participants[0]["email"] = None
    ev2.participants[0]["status"] = "yes"
    merged_participants = ev._partial_participants_merge(ev2)

    assert len(merged_participants) == 3

    for participant in merged_participants:
        if participant["email"] is None:
            assert participant["status"] == "yes"
        elif participant["email"] == "ronald@mcdonalds.com":
            assert participant["name"] == "Ronald McDonald"
        elif participant["email"] == "ronald@example.com":
            assert participant["name"] == "Ronald Zubar"
