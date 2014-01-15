from flanker.addresslib import address

from .misc import or_none

def strip_quotes(display_name):
    if display_name.startswith('"') and display_name.endswith('"'):
        return display_name[1:-1]
    else:
        return display_name

def parse_email_address(email_address):
    parsed = address.parse(email_address)
    return or_none(parsed, lambda p: (strip_quotes(p.display_name), p.address))
