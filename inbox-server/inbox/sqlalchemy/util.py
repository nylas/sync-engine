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
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if not value:
            return None
        return json.loads(value)

class LittleJSON(JSON):
    impl = String(40)

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
