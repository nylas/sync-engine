"""
This module provides utilities for encoding data into compressed/encrypted
binary blobs. These have the following data format:

|<1 byte>|
+--------+--------+--------+--------+--------+--------+--------+--------+-----
| scheme |              key version          |               data
+--------+--------+--------+--------+--------+--------+--------+--------+-----

The "scheme" byte can be used to version the data format. Currently the only
values are 0 (no encryption) and 1 (encryption with a static key). The key
version bytes can be used to rotate encryption keys. (Right now these are
always just null bytes.)
"""
import struct
import zlib
from inbox.security.oracles import get_encryption_oracle, get_decryption_oracle


KEY_VERSION = 0
HEADER_WIDTH = 5


def _pack_header(scheme):
    return struct.pack('<BI', scheme, KEY_VERSION)


def _unpack_header(header):
    scheme, key_version = struct.unpack('<BI', header)
    assert key_version == KEY_VERSION
    return scheme


def encode_blob(plaintext):
    assert isinstance(plaintext, bytes), 'Plaintext should be bytes'
    compressed = zlib.compress(plaintext)
    encryption_oracle = get_encryption_oracle('BLOCK_ENCRYPTION_KEY')
    ciphertext, scheme = encryption_oracle.encrypt(compressed)
    header = _pack_header(scheme)
    return header + ciphertext


def decode_blob(blob):
    header = blob[:HEADER_WIDTH]
    body = blob[HEADER_WIDTH:]
    scheme = _unpack_header(header)
    decryption_oracle = get_decryption_oracle('BLOCK_ENCRYPTION_KEY')
    compressed_plaintext = decryption_oracle.decrypt(body, scheme)
    result = zlib.decompress(compressed_plaintext)
    return result
