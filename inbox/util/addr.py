from flanker.addresslib import address

from inbox.util.misc import or_none


# TODO we should probably just store flanker's EmailAddress object
# instead of doing this thing with quotes ourselves
def strip_quotes(display_name):
    if display_name.startswith('"') and display_name.endswith('"'):
        return display_name[1:-1]
    else:
        return display_name


def parse_email_address_list(email_addresses):
    parsed = address.parse_list(email_addresses)
    return [or_none(addr, lambda p:
            (strip_quotes(p.display_name), p.address)) for addr in parsed]
