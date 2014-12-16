import abc
import uuid
import struct
import time
from datetime import datetime

from bson import json_util, EPOCH_NAIVE
# Monkeypatch to not include tz_info in decoded JSON.
# Kind of a ridiculous solution, but works.
json_util.EPOCH_AWARE = EPOCH_NAIVE

from sqlalchemy import String, Text, event
from sqlalchemy.types import TypeDecorator, BINARY
from sqlalchemy.interfaces import PoolListener
from sqlalchemy.engine import Engine
from sqlalchemy.ext.mutable import Mutable
from sqlalchemy.ext.declarative import DeclarativeMeta

from inbox.util.encoding import base36encode, base36decode

from inbox.log import get_logger
log = get_logger()


SLOW_QUERY_THRESHOLD_MS = 5000
MAX_TEXT_LENGTH = 65535


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement,
                          parameters, context, executemany):
    context._query_start_time = time.time()


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement,
                         parameters, context, executemany):
    total = int(1000 * (time.time() - context._query_start_time))
    # We only care about slow reads here
    if total > SLOW_QUERY_THRESHOLD_MS and statement.startswith('SELECT'):
        statement = ' '.join(statement.split())
        try:
            log.warning('slow query', query_time=total, statement=statement,
                        parameters=parameters)
        except UnicodeDecodeError:
            log.warning('slow query', query_time=total)
            log.error('logging UnicodeDecodeError')


class SQLAlchemyCompatibleAbstractMetaClass(DeclarativeMeta, abc.ABCMeta):
    """Declarative model classes that *also* inherit from an abstract base
    class need a metaclass like this one, in order to prevent metaclass
    conflict errors."""
    pass


class ABCMixin(object):
    """Use this if you want a mixin class which is actually an abstract base
    class, for example in order to enforce that concrete subclasses define
    particular methods or properties."""
    __metaclass__ = SQLAlchemyCompatibleAbstractMetaClass
    __abstract__ = True


# Column Types


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


def json_field_too_long(value):
    return len(json_util.dumps(value)) > MAX_TEXT_LENGTH


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


# http://docs.sqlalchemy.org/en/rel_0_9/orm/extensions/mutable.html#sqlalchemy.ext.mutable.Mutable.as_mutable
# Can simply use this as is because though we use bson.json_util, loads()
# dumps() return standard Python dicts like the json.* equivalents
# (because these are simply called under the hood)
class MutableDict(Mutable, dict):
    @classmethod
    def coerce(cls, key, value):
        """ Convert plain dictionaries to MutableDict. """
        if not isinstance(value, MutableDict):
            if isinstance(value, dict):
                return MutableDict(value)

            # this call will raise ValueError
            return Mutable.coerce(key, value)
        else:
            return value

    def __setitem__(self, key, value):
        """ Detect dictionary set events and emit change events. """
        dict.__setitem__(self, key, value)
        self.changed()

    def __delitem__(self, key):
        """ Detect dictionary del events and emit change events. """
        dict.__delitem__(self, key)
        self.changed()

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).iteritems():
            self[k] = v

    # To support pickling:
    def __getstate__(self):
        return dict(self)

    def __setstate__(self, state):
        self.update(state)


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
    """ Returns a base-36 string UUID """
    u = uuid.uuid4().bytes
    return int128_to_b36(u)


# Other utilities

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


def safer_yield_per(query, id_field, start_id, count):
    """Incautious execution of 'for result in query.yield_per(N):' may cause
    slowness or OOMing over large tables. This is a less general but less
    dangerous alternative.

    Parameters
    ----------
    query: sqlalchemy.Query
        The query to yield windowed results from.
    id_field: A SQLAlchemy attribute to use for windowing. E.g.,
        `Transaction.id`
    start_id: The value of id_field at which to start iterating.
    count: int
        The number of results to fetch at a time.
    """
    while True:
        results = query.filter(id_field >= start_id).limit(count).all()
        if not results:
            return
        for result in results:
            start_id = result.id + 1
            yield result
