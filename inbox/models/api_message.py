import json
import re
from datetime import datetime
from sqlalchemy import Column, BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.mysql import LONGBLOB

from inbox.models.api_thread import ApiThread
from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace
from inbox.sqlalchemy_ext.util import Base36UID


class ApiMessage(MailSyncBase):
    id = Column(BigInteger, primary_key=True, autoincrement=False)
    public_id = Column(Base36UID, nullable=False)
    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'), nullable=False)
    value = Column(LONGBLOB(), nullable=False)
    expanded_value = Column(LONGBLOB(), nullable=False)

    # needed to load raw messages from block store
    data_sha256 = Column(String(255), nullable=True)

    # needed for indexes (TODO create indexes!)
    categories = Column(Text(), nullable=False)
    subject = Column(String(255), nullable=True, default='')
    thread_public_id = Column(Base36UID, nullable=False)

    def __repr__(self):
        return '<ApiMessage(id=%d, public_id=%s)>' % (self.id, self.public_id)

    @classmethod
    def from_obj(cls, obj):
        return cls(**cls.params_from_obj(obj))

    @classmethod
    def params_from_obj(cls, obj):
        from inbox.models.message import Message
        from inbox.api.kellogs import encode

        if isinstance(obj, Message):
            id = obj.id
            public_id = obj.public_id
            json = _dumps(encode(obj))
            expanded_json = _dumps(encode(obj, expand=True))

            categories = obj.categories
            pat = re.compile(',')
            def escape_commas(category):
                return pat.sub('COMMA', category.display_name)
            catfield = ','.join(map(escape_commas, categories))

            return dict(id=id, public_id=public_id, namespace_id=obj.namespace.id,
                    data_sha256=obj.data_sha256,

                    categories=catfield,
                    subject=obj.subject,
                    thread_public_id=obj.thread.public_id,

                    value=json,
                    expanded_value=expanded_json
            )
        else:
            raise TypeError("%s.from_obj can't handle %s" % (cls, type(obj)))

    def as_json(self, view=None):
        if view == 'expanded':
            return self.expanded_value
        elif view is None:
            return self.value
        else:
            raise ValueError('Invalid view parameter: %s' % view)


EPOCH = datetime.utcfromtimestamp(0)

def _dumps(obj):
    def serialize_with_epoch_time(obj):
        if isinstance(obj, datetime):
            epoch_seconds = (obj - EPOCH).total_seconds()
            return epoch_seconds
        raise TypeError('Type not serializable')
    return json.dumps(obj, default=serialize_with_epoch_time)
