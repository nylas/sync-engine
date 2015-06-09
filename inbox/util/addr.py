import rfc822
from flanker.addresslib import address
from flanker.mime.message.headers.parsing import normalize
from flanker.mime.message.headers.encodedword import decode


def canonicalize_address(addr):
    """Gmail addresses with and without periods are the same."""
    parsed_address = address.parse(addr, addr_spec_only=True)
    if not isinstance(parsed_address, address.EmailAddress):
        return addr
    local_part = parsed_address.mailbox.lower()
    hostname = parsed_address.hostname.lower()
    if hostname in ('gmail.com', 'googlemail.com'):
        local_part = local_part.replace('.', '')
    return '@'.join((local_part, hostname))


def parse_mimepart_address_header(mimepart, header_name):
    # Header parsing is complicated by the fact that:
    # (1) You can have multiple occurrences of the same header;
    # (2) Phrases or comments can be RFC2047-style encoded words;
    # (3) Everything is terrible.
    # Here, for each occurrence of the header in question, we first parse
    # it into a list of (phrase, addrspec) tuples and then use flanker to
    # decode any encoded words.
    # You want to do it in that order, because otherwise if you get a header
    # like
    # From: =?utf-8?Q?FooCorp=2C=20Inc.=? <info@foocorp.com>
    # you can end up parsing 'FooCorp, Inc. <info@foocorp.com> (note lack of
    # quoting) into two separate addresses.
    # Consult RFC822 Section 6.1 and RFC2047 section 5 for details.
    addresses = set()
    for section in mimepart.headers._v.getall(normalize(header_name)):
        for phrase, addrspec in rfc822.AddressList(section).addresslist:
            addresses.add((decode(phrase), decode(addrspec)))

    # Return a list of lists because it makes it easier to compare an address
    # field to one which has been fetched from the db.
    return sorted(list(elem) for elem in addresses)
