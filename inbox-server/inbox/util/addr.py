from flanker.addresslib import address

from .misc import or_none

def parse_email_address(email_address):
    parsed = address.parse(email_address)
    return or_none(parsed, lambda p: (p.display_name, p.address))
