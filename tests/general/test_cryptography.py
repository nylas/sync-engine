import pytest

from inbox.util.cryptography import encrypt_aes, decrypt_aes

@pytest.fixture
def plaintext_message():
    return "my super secret test message"


def test_encrypt_decrypt(plaintext_message):
    """
    Tests that encryption followed by decryption gives back the original
    message.
    """
    assert decrypt_aes(*encrypt_aes(plaintext_message)) == plaintext_message

def test_key_length_respected(plaintext_message):
    """
    Tests that encrypt_aes respects the key_length argument when generating a
    key.
    """
    for key_length in [128, 256, 192]:
        _, key = encrypt_aes(plaintext_message, key_length)
        assert len(key) == key_length / 8

def test_bad_key_lengths(plaintext_message):
    """
    Tests that encrypt_aes throws a ValueError when passed a bad key length.
    """
    with pytest.raises(ValueError):
        encrypt_aes(plaintext_message, 0)
    with pytest.raises(ValueError):
        encrypt_aes(plaintext_message, -1)
    with pytest.raises(ValueError):
        encrypt_aes(plaintext_message, 127)


