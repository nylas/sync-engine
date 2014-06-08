""" Revision mixin class based on SQLAlchemy "versioned_history" example.

https://github.com/zzzeek/sqlalchemy/blob/master/examples/versioned_history/history_meta.py

Our goal is only to make it easy to get a log of changes that have happened
since a given revision, not to make it easy to access any given object at any
given point in history, which makes our implementation much simpler: instead of
generating corresponding "history" tables with historical versions, we have one
master Revision table that logs deltas as JSON.

Requires sqlalchemy 0.8, for the inspect API.

Revisions of related collections are optionally recorded if the relationship's
'info' dictionary contains a 'versioned_properties' key. Specifically,
info['versioned_properties'] should be a list of properties on the related
object to record (in the revision log entry for the parent) whenever the
collection changes. The following example illustrates.

This code:
----------------------------------------
class SomeClass(Base, HasRevisions):
    related_id = Column(Integer, ForeignKey('SomeRelated.id'))

    related = relationship('SomeRelated', info={'versioned_properties':
                                                ['name', 'value']})

class SomeRelated(Base):
    someclass_id = Column(Integer, ForeignKey('SomeClass.id'))

    someclass = relationship('SomeClass',
                             backref=backref('somerelated',
                                             info={'versioned_properties':
                                                   ['name', 'value']}))
    name = Column(String(64))
    value = Column(Integer)
    other = Column(String(64))


s = SomeClass()
r1 = SomeRelated(name='foo', value=22, other='fluff')
r2 = SomeRelated(name='bar', value=2222, other='more fluff')
s.related.append(r1)
s.related.append(r2)

session.add(s)
session.commit()
----------------------------------------

would produce this delta in the transaction log:

----------------------------------------
{'related': {'added': [{'name': 'foo', 'value': 22},
                       {'name': 'bar', 'value': 2222}],
             'unchanged': [],
             'deleted': []}}
----------------------------------------

The versioned properties of unchanged and deleted children appear similarly.
See the tests for more examples. (TODO(emfree): actually write some tests.)
"""

from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy import event, inspect
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import UnmappedColumnError
from sqlalchemy.orm.properties import RelationshipProperty
from sqlalchemy.ext.declarative import declared_attr

from .util import BigJSON


class Revision(object):
    """ All revision records in a single table (role). """
    # Which object are we recording changes to?
    table_name = Column(String(20), nullable=False, index=True)
    record_id = Column(Integer, nullable=False)

    command = Column(Enum('insert', 'update', 'delete'), nullable=False)
    delta = Column(BigJSON, nullable=True)

    additional_data = Column(BigJSON)

    def set_extra_attrs(self, obj):
        pass

    def set_additional_data(self, obj):
        self.additional_data = obj.get_versioned_properties()


def gen_rev_role(rev_cls):
    """ Generate generic HasRevisions mixin.

    Use this if you subclass Revision.
    """
    class HasRevisions(object):
        """ Generic mixin which creates a read-only revisions attribute on the
            class for convencience.
        """
        @declared_attr
        def revisions(cls):
            return relationship(rev_cls,
                                primaryjoin="{0}.id=={1}.record_id".format(
                                    cls.__name__, rev_cls.__name__),
                                foreign_keys=rev_cls.record_id, viewonly=True)

        def get_versioned_properties(self):
            """Subclasses which wish to store data in the transaction log's
            `additional_data` field should implement this method, returning a
            serializable dictionary."""
            pass

    return HasRevisions


def create_insert_revision(rev_cls, obj, session):
    d = delta(obj)
    assert d, "Can't insert object {0}:{1} with no delta".format(
        obj.__tablename__, obj.id)
    return rev_cls(command='insert', record_id=obj.id,
                   table_name=obj.__tablename__, delta=d)


def create_delete_revision(rev_cls, obj, session):
    # NOTE: The application layer needs to deal with purging all history
    # related to the object at some point.
    return rev_cls(command='delete', record_id=obj.id,
                   table_name=obj.__tablename__)


def create_update_revision(rev_cls, obj, session):
    d = delta(obj)
    # sqlalchemy objects can be dirty even if they haven't changed
    if not d:
        return
    return rev_cls(command='update', record_id=obj.id,
                   table_name=obj.__tablename__, delta=d)


def _get_properties(properties, items):
    return [{prop: getattr(item, prop) for prop in properties}
            for item in items]


def delta(obj):
    obj_state = inspect(obj)

    obj_changed = False
    d = {}

    for prop in obj_state.mapper.iterate_properties:
        if (isinstance(prop, RelationshipProperty) and
                'versioned_properties' in prop.info):
            history = getattr(obj_state.attrs, prop.key).history
            if not history.has_changes():
                continue
            changes = {}
            versioned_properties = prop.info['versioned_properties']
            changes['added'] = _get_properties(versioned_properties,
                                               history.added)
            changes['unchanged'] = _get_properties(versioned_properties,
                                                   history.unchanged)
            changes['deleted'] = _get_properties(versioned_properties,
                                                 history.deleted)
            d[prop.key] = changes
            obj_changed = True

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

            added, unchanged, deleted = getattr(
                obj_state.attrs, prop.key).history
            if added:
                # if the attribute had no value.
                d[col.key] = added[0]
                obj_changed = True
            elif deleted:
                d[col.key] = deleted[0]
                obj_changed = True
            # do nothing for unchanged

        if not obj_changed:
            # not changed, but we have relationships.  OK
            # check those too
            for prop in obj_state.mapper.iterate_properties:
                if isinstance(prop, RelationshipProperty) and getattr(
                        obj_state.attrs, prop.key).history.has_changes():
                    for p in prop.local_columns:
                        if p.foreign_keys:
                            obj_changed = True
                            break
                    if obj_changed is True:
                        break

        if not obj_changed:
            return

    return d


def versioned_session(session, rev_cls, rev_role):
    def create_revision(session, obj, create_fn):
        if isinstance(obj, rev_role):
            rev = create_fn(rev_cls, obj, session)
            if rev is not None:
                rev.set_extra_attrs(obj)
                rev.set_additional_data(obj)
                session.add(rev)

    @event.listens_for(session, 'after_flush')
    def after_flush(session, flush_context):
        """ Hook to log revision deltas. Must be post-flush in order to grab
            object IDs on new objects.
        """
        for obj in session.new:
            create_revision(session, obj, create_insert_revision)
        for obj in session.dirty:
            create_revision(session, obj, create_update_revision)
        for obj in session.deleted:
            create_revision(session, obj, create_delete_revision)

    return session
