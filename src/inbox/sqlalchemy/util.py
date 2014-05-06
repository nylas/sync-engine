import uuid
import struct

from bson import json_util

from sqlalchemy import String, Text
from sqlalchemy.types import TypeDecorator, BINARY
from sqlalchemy.interfaces import PoolListener

from inbox.util.encoding import base36encode, base36decode

### Column Types


# http://docs.sqlalchemy.org/en/rel_0_9/core/types.html#marshal-json-strings
class JSON(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json_util.dumps(value)

    def process_result_value(self, value, dialect):
        if not value:
            return None
        return json_util.loads(value)


class LittleJSON(JSON):
    impl = String(255)


class BigJSON(JSON):
    # if all characters were 4-byte, this would fit in mysql's MEDIUMTEXT
    impl = Text(4194304)


class Base36UID(TypeDecorator):
    impl = BINARY(16)  # 128 bit unsigned integer

    def process_bind_param(self, value, dialect):
        if not value:
            return None
        return b36_to_bin(value)

    def process_result_value(self, value, dialect):
        return int128_to_b36(value)


def int128_to_b36(int128):
    """ int128: a 128 bit unsigned integer
        returns a base-36 string representation
    """
    if not int128:
        return None
    assert len(int128) == 16, "should be 16 bytes (128 bits)"
    a, b = struct.unpack('>QQ', int128)  # uuid() is big-endian
    pub_id = (a << 64) | b
    return base36encode(pub_id).lower()


def b36_to_bin(b36_string):
    """ b36_string: a base-36 encoded string
        returns binary 128 bit unsigned integer
    """
    int128 = base36decode(b36_string)
    MAX_INT64 = 0xFFFFFFFFFFFFFFFF
    return struct.pack(
        '>QQ',
        (int128 >> 64) & MAX_INT64,
        int128 & MAX_INT64)


def generate_public_id():
    """ Returns at base-36 string UUID """
    u = uuid.uuid4().bytes
    return int128_to_b36(u)


### Other utilities

# My good old friend Enrico to the rescue:
# http://www.enricozini.org/2012/tips/sa-sqlmode-traditional/
#
# We set sql-mode=traditional on the server side as well, but enforce at the
# application level to be extra safe.
#
# Without this, MySQL will silently insert invalid values in the database if
# not running with sql-mode=traditional.
class ForceStrictMode(PoolListener):
    def connect(self, dbapi_con, connection_record):
        cur = dbapi_con.cursor()
        cur.execute("SET SESSION sql_mode='TRADITIONAL'")
        cur = None


def maybe_refine_query(query, subquery):
    if subquery is None:
        return query
    return query.join(subquery.subquery())
