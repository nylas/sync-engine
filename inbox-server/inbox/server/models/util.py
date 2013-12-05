import json

from sqlalchemy.types import TypeDecorator
from sqlalchemy import String, Text

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
