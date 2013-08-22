import itertools

def chunk(iterable, size):
    """ Yield chunks of an iterable.

    If len(iterable) is not evenly divisible by size, the last chunk will be
    shorter than size.
    """
    it = iter(iterable)
    while True:
        group = tuple(itertools.islice(it, None, size))
        if not group:
            break
        yield group
