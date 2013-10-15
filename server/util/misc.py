def or_none(value, selector):
    if value is None:
        return None
    else:
        return selector(value)
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
