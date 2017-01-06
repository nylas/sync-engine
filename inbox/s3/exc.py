class S3Exception(Exception):
    pass


class EmailFetchException(S3Exception):
    pass


class EmailDeletedException(EmailFetchException):
    """Raises an error when the message is deleted on the remote."""
    pass


class TemporaryEmailFetchException(EmailFetchException):
    """A class for temporary errors when trying to fetch emails.
    Exchange notably seems to need warming up before fetching data."""
    pass
