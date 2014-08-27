# -*- coding: utf-8 -*-
"""Regression tests for HTML parsing."""
from inbox.util.html import strip_tags


def test_strip_tags():
    text = ('<div><script> AAH JAVASCRIPT</script><style> AAH CSS AHH</style>'
            'check out this <a href="http://example.com">link</a> yo!</div>')
    assert strip_tags(text) == 'check out this link yo!'


def test_preserve_refs():
    """Test that HTML character/entity references are preserved when we strip
    tags."""
    text = u'la philologie m&#x00e8;ne au pire'
    assert strip_tags(text) == u'la philologie mène au pire'

    text = u'la philologie m&#232;ne au pire'
    assert strip_tags(text) == u'la philologie mène au pire'

    text = u'veer &amp; wander'
    assert strip_tags(text) == 'veer & wander'
