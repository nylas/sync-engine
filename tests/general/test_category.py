# -*- coding: utf-8 -*-
from inbox.models import Folder, Label
from inbox.models.category import sanitize_name
from inbox.models.constants import MAX_INDEXABLE_LENGTH
from tests.util.base import (add_fake_folder, add_fake_label, generic_account,
                             gmail_account, db)

__all__ = ['db', 'generic_account', 'gmail_account']

def test_category_sanitize_name():
    assert sanitize_name(42) == u'42'
    assert sanitize_name('42') == u'42'
    assert sanitize_name(u'  Boîte de réception  ') ==\
                                  u'  Boîte de réception'
    long_name = 'N' * (MAX_INDEXABLE_LENGTH + 10)
    assert sanitize_name(long_name) == 'N' * MAX_INDEXABLE_LENGTH

    long_name = 'N' * (MAX_INDEXABLE_LENGTH - 2) + '  '
    assert sanitize_name(long_name) == 'N' * (MAX_INDEXABLE_LENGTH - 2)

def test_folder_sanitized(db, generic_account):
    long_name = 'F' * (MAX_INDEXABLE_LENGTH + 10)
    folder = add_fake_folder(db.session, generic_account, long_name)
    assert len(folder.name) == MAX_INDEXABLE_LENGTH

    # Test that we get back the correct model even when querying with a long
    # name
    found = db.session.query(Folder).filter(Folder.name == long_name).one()
    assert len(found.name) == MAX_INDEXABLE_LENGTH
    assert folder.id == found.id
    assert found.name == folder.name

def test_label_sanitized(db, gmail_account):
    long_name = 'L' * (MAX_INDEXABLE_LENGTH + 10)
    label = add_fake_label(db.session, gmail_account, long_name)
    assert len(label.name) == MAX_INDEXABLE_LENGTH

    # Test that we get back the correct model even when querying with a long
    # name
    found = db.session.query(Label).filter(Label.name == long_name).one()
    assert len(found.name) == MAX_INDEXABLE_LENGTH
    assert label.id == found.id
    assert found.name == label.name
