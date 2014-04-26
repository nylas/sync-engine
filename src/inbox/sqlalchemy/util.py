from bson import json_util

import json

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.types import TypeDecorator
from sqlalchemy.interfaces import PoolListener

from sqlalchemy.ext.declarative import as_declarative, declared_attr


### Column Types

# http://docs.sqlalchemy.org/en/rel_0_9/core/types.html#marshal-json-strings
class JSON(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, default=json_util.default)

    def process_result_value(self, value, dialect):
        if not value:
            return None
        return json.loads(value, object_hook=json_util.object_hook)


class LittleJSON(JSON):
    impl = String(255)


class BigJSON(JSON):
    # if all characters were 4-byte, this would fit in mysql's MEDIUMTEXT
    impl = Text(4194304)


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


@as_declarative()
class Base(object):
    """Base class which provides automated table name
    and surrogate primary key column.
    """
    id = Column(Integer, primary_key=True, autoincrement=True)

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    @declared_attr
    def __table_args__(cls):
        return {'extend_existing': True}
