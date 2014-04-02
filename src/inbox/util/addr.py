from flanker.addresslib import address

from .misc import or_none

def strip_quotes(display_name):
    if display_name.startswith('"') and display_name.endswith('"'):
        return display_name[1:-1]
    else:
        return display_name

def parse_email_address_list(email_addresses):
    parsed = address.parse_list(email_addresses)
    return [or_none(addr, lambda p:
        (strip_quotes(p.display_name), p.address)) for addr in parsed]


def parse_email_address(email_address):
    parsed = parse_email_address_list(email_address)
    if len(parsed) == 0: return None
    assert len(parsed) == 1, 'Expected only one address' + str(parsed)
    return parsed[0]
