# Backport from Python 3.2
# Custom SSLContext may be passed starting from Python 2.7.9.
# http://hg.python.org/cpython/rev/8d6516949a71/
import imaplib
import re
import ssl

Commands = {
    'STARTTLS': ('NONAUTH')
}
imaplib.Commands.update(Commands)

def starttls(self, ssl_context=None):
    name = 'STARTTLS'
    if self._tls_established:
        raise self.abort('TLS session already established')
    if name not in self.capabilities:
        raise self.abort('TLS not supported by server')
    # Generate a default SSL context if none was passed.
    if ssl_context is None:
        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        except AttributeError:
            # Python < 2.7.9
            ssl_context = None
        else:
            # SSLv2 considered harmful.
            ssl_context.options |= ssl.OP_NO_SSLv2
    # Generate a default SSL context if none was passed.
    typ, dat = self._simple_command(name)
    if typ == 'OK':
        if ssl_context:
            self.sock = ssl_context.wrap_socket(self.sock)
        else:
            self.sock = ssl.wrap_socket(self.sock)
        self.file = self.sock.makefile('rb')
        self._tls_established = True
        typ, dat = self.capability()
        if dat == [None]:
            raise self.error('no CAPABILITY response from server')
        self.capabilities = tuple(dat[-1].upper().split())
    else:
        raise self.error("Couldn't establish TLS session")
    return self._untagged_response(typ, dat, name)

imaplib.IMAP4._tls_established = False
imaplib.IMAP4.starttls = starttls
