def base36encode(number):
    if not isinstance(number, (int, long)):
        raise TypeError('number must be an integer')
    if number < 0:
        raise ValueError('number must be positive')

    alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

    base36 = ''
    while number:
        number, i = divmod(number, 36)
        base36 = alphabet[i] + base36

    return base36 or alphabet[0]


def base36decode(number):
    return int(number, 36)


# From: http://stackoverflow.com/a/1820949
# Quick and dirty hack to truncate a unicode string
# on a codepoint boundary.
def unicode_truncate(s, new_length):
    assert isinstance(s, unicode)
    encoded = s.encode('utf-8')[:new_length]

    # This assumes that we've been able to decode the string
    # to unicode in the first place, so any errors would be
    # caused by the truncation.
    return encoded.decode('utf-8', 'ignore')
