from flanker.addresslib import address

from inbox.util.misc import or_none


def canonicalize_address(addr):
    """Gmail addresses with and without periods are the same."""
    parsed_address = address.parse(addr, addr_spec_only=True)
    if not isinstance(parsed_address, address.EmailAddress):
        return addr
    local_part = parsed_address.mailbox
    if parsed_address.hostname in ('gmail.com', 'googlemail.com'):
        local_part = local_part.replace('.', '')
    return '@'.join((local_part, parsed_address.hostname))


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


def parse_mimepart_address_header(mimepart, header_name):
    return parse_email_address_list(mimepart.headers.getall(header_name))
