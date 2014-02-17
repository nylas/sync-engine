import os
from Crypto import Random
from Crypto.Cipher import AES

from inbox.server.config import config

KEY_SIZE = int(config.get('KEY_SIZE', 128))

# The AES functions below are implemented using Python's Crypto library and
# this blog: http://www.commx.ws/2013/10/aes-encryption-with-python/
def encrypt_aes(message):
    """
    AES encrypts a message using a generated random key of KEY_SIZE
    (default is 128 bits)
    The function expects the message as a byte string; it returns a tuple of
    the encrypted message as a byte string, and the key.
    """
    # Convert string message to a bytes object, needed for ops below
    if type(message) == unicode:
        message = message.encode('utf-8')

    # PKCS#7 padding scheme
    def pad(s):
        pad_length = AES.block_size - (len(s) % AES.block_size)
        return s + (chr(pad_length) * pad_length)

    padded_message = pad(message)

    key = Random.OSRNG.posix.new().read(KEY_SIZE // 8)
    iv = Random.OSRNG.posix.new().read(AES.block_size)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return ((iv + cipher.encrypt(padded_message)), key)

def decrypt_aes(ciphertext, key):
    """
    Decrypts a ciphertext that was AES-encrypted with the given key.
    The function expects the ciphertext as a byte string and it returns the
    decrypted message as a byte string.
    """
    unpad = lambda s: s[:-ord(s[-1])]
    iv = ciphertext[:AES.block_size]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = unpad(cipher.decrypt(ciphertext))[AES.block_size:]
    return plaintext