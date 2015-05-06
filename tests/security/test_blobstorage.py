import zlib
import hypothesis
from inbox.security.blobstorage import encode_blob, decode_blob


# This will run the test for a bunch of randomly-chosen values of sample_input.
@hypothesis.given(str, bool)
def test_blobstorage(config, sample_input, encrypt):
    config['ENCRYPT_SECRETS'] = encrypt
    assert decode_blob(encode_blob(sample_input)) == sample_input


@hypothesis.given(str, bool)
def test_encoded_format(config, sample_input, encrypt):
    config['ENCRYPT_SECRETS'] = encrypt
    encoded = encode_blob(sample_input)
    assert encoded.startswith(chr(encrypt) + '\x00\x00\x00\x00')
    data = encoded[5:]
    if encrypt:
        assert data != sample_input
        assert data != zlib.compress(sample_input)
    else:
        assert data == zlib.compress(sample_input)


@hypothesis.given(unicode, bool)
def test_message_body_storage(config, message, sample_input, encrypt):
    config['ENCRYPT_SECRETS'] = encrypt
    message.body = None
    assert message._compacted_body is None
    message.body = sample_input
    assert message._compacted_body.startswith(
        chr(encrypt) + '\x00\x00\x00\x00')
    assert message.body == sample_input
