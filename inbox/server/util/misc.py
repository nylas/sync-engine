def or_none(value, selector):
    if value is None:
        return None
    else:
        return selector(value)
