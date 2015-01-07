import rfc822
from flanker.addresslib import address


def canonicalize_address(addr):
    """Gmail addresses with and without periods are the same."""
    parsed_address = address.parse(addr, addr_spec_only=True)
    if not isinstance(parsed_address, address.EmailAddress):
        return addr
    local_part = parsed_address.mailbox
    if parsed_address.hostname in ('gmail.com', 'googlemail.com'):
        local_part = local_part.replace('.', '')
    return '@'.join((local_part, parsed_address.hostname))


def parse_mimepart_address_header(mimepart, header_name):
    header_list_string = ', '.join(mimepart.headers.getall(header_name))
    addresslist = rfc822.AddressList(header_list_string).addresslist
    if len(addresslist) > 1:
        # Deduplicate entries
        return list(set(addresslist))
    return addresslist
