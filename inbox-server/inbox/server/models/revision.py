""" Revision mixin class based on SQLAlchemy "versioned_history" example.

https://github.com/zzzeek/sqlalchemy/blob/master/examples/versioned_history/history_meta.py

Our goal is only to make it easy to get a log of changes that have happened
since a given revision, not to make it easy to access any given object at any
given point in history, which makes our implementation much simpler: instead of
generating corresponding "history" tables with historical versions, we have one
master Revision table that logs deltas as JSON.
"""

from sqlalchemy import Column, Integer, Enum
from sqlalchemy import event, inspect
from sqlalchemy.orm.exc import UnmappedColumnError
from sqlalchemy.orm.properties import RelationshipProperty

from .util import JSON

class Revision(object):
    id = Column(Integer, primary_key=True, autoincrement=True)

    command = Column(Enum('add', 'update', 'delete'), nullable=False)
    delta = Column(JSON, nullable=False)

def create_revision(rev_cls, obj, session, deleted=False):
    rev = rev_cls()
    if deleted:
        rev.command = 'delete'
    else:
        obj_state = inspect(obj)
        if obj_state.modified:
            rev.command = 'update'
        else:
            assert obj_state.pending
            rev.command = 'add'

    attr = {}
    obj_changed = False

    for m in obj_state.mapper.iterate_to_root():
        for col in m.local_table.c:
            # get the value of the attribute based on the MapperProperty
            # related to the mapped column. this will allow usage of
            # MapperProperties that have a different keyname than that of the
            # mapped column.
            try:
                prop = obj_state.mapper.get_property_by_column(col)
            except UnmappedColumnError:
                # in the case of single table inheritance, there may be columns
                # on the mapped table intended for the subclass only. the
                # "unmapped" status of the subclass column on the base class is
                # a feature of the declarative module as of sqla 0.5.2.
                continue

            # expired object attributes and also deferred cols might not be in
            # the dict. force it to load no matter what by using getattr().
            if prop.key not in obj_state.dict:
                getattr(obj, prop.key)

            a, u, d = obj_state.get_history(obj, prop.key)
            if d:
                attr[col.key] = d[0]
                obj_changed = True
            elif u:
                pass
            else:
                # if the attribute had no value.
                attr[col.key] = a[0]
                obj_changed = True

        if not obj_changed:
            # not changed, but we have relationships.  OK
            # check those too
            for prop in obj_state.mapper.iterate_properties:
                if isinstance(prop, RelationshipProperty) and \
                    obj_state.get_history(obj, prop.key).has_changes():
                    for p in prop.local_columns:
                        if p.foreign_keys:
                            obj_changed = True
                            break
                    if obj_changed is True:
                        break

        if not obj_changed and not deleted:
            return

        for key, value in attr.items():
            setattr(rev, key, value)
        session.add(rev)

def versioned_session(session, rev_cls=Revision):
    @event.listens_for(session, 'before_flush')
    def before_flush(db_session, flush_context, instances):
        """ Hook to log revision deltas. """
        for obj in session.dirty:
            create_revision(rev_cls, obj, session)
        for obj in session.deleted:
            create_revision(rev_cls, obj, session, deleted=True)
