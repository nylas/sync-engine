import json
import re
from datetime import datetime
from sqlalchemy import Column, BigInteger, DateTime, ForeignKey, String, Text, desc
from sqlalchemy.dialects.mysql import LONGBLOB

from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace
from inbox.sqlalchemy_ext.util import Base36UID, JSON

class ApiPatchThread(MailSyncBase):
    id = Column(BigInteger, primary_key=True, autoincrement=False)
    public_id = Column(Base36UID, nullable=False)
    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'), nullable=False)
    value = Column(LONGBLOB(), nullable=False)
    expanded_value = Column(LONGBLOB(), nullable=False)

    def __repr__(self):
        return '<ApiPatchThread(id=%d, public_id=%s)>' % (self.id, self.public_id)

    @classmethod
    def from_obj(cls, obj):
        return cls(**cls.params_from_obj(obj))

    @classmethod
    def params_from_obj(cls, obj):
        from inbox.models.thread import Thread
        from inbox.api.kellogs import encode

        if isinstance(obj, Thread):
            id = obj.id
            public_id = obj.public_id
            json = _dumps(encode(obj))
            expanded_json = _dumps(encode(obj, expand=True))

            return dict(id=id, public_id=public_id, namespace_id=obj.namespace.id,
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


class ApiThread(MailSyncBase):
    id = Column(BigInteger, primary_key=True, autoincrement=False)
    public_id = Column(Base36UID, nullable=False)
    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'), nullable=False)
    value = Column(LONGBLOB(), nullable=False)
    expanded_value = Column(LONGBLOB(), nullable=False)

    # needed for ordering
    recentdate = Column(DateTime, nullable=False)
    api_ordering = desc(recentdate)

    categories = Column(JSON(), nullable=False)
    subject = Column(String(255), nullable=True, default='')
    from_addrs = Column(JSON(), nullable=False)
    to_addrs = Column(JSON(), nullable=False)
    cc_addrs = Column(JSON(), nullable=False)
    bcc_addrs = Column(JSON(), nullable=False)

    def __repr__(self):
        return '<ApiThread(id=%d, public_id=%s)>' % (self.id, self.public_id)

    PATCH_TABLE = ApiPatchThread

    @classmethod
    def from_obj(cls, obj):
        return cls(**cls.params_from_obj(obj))

    @classmethod
    def params_from_obj(cls, obj):
        from inbox.models.thread import Thread
        from inbox.api.kellogs import encode

        if isinstance(obj, Thread):
            id = obj.id
            public_id = obj.public_id
            json = _dumps(encode(obj))
            expanded_json = _dumps(encode(obj, expand=True))

            category_names = map(lambda cat: cat.name, obj.categories)
            category_display_names = map(lambda cat: cat.display_name, obj.categories)

            froms = set()
            tos = set()
            ccs = set()
            bccs = set()
            # based on Thread.participants
            for m in obj.messages:
                if m.is_draft:
                    continue
                for _, address in m.from_addr: froms.add(address)
                for _, address in m.to_addr: tos.add(address)
                for _, address in m.cc_addr: ccs.add(address)
                for _, address in m.bcc_addr: bccs.add(address)

            return dict(id=id, public_id=public_id, namespace_id=obj.namespace.id,
                    recentdate=obj.recentdate,
                    categories=category_names + category_display_names,
                    subject=obj.subject,
                    from_addrs=froms,
                    to_addrs=tos,
                    cc_addrs=ccs,
                    bcc_addrs=bccs,

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
