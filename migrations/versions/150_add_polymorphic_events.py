"""Add polymorphic Events

Revision ID: 1de526a15c5d
Revises: 2493281d621
Create Date: 2015-03-11 22:51:22.180028

"""

# revision identifiers, used by Alembic.
revision = '1de526a15c5d'
down_revision = '2493281d621'

import json
import ast
import sys
from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'recurringeventoverride',
        sa.Column('id', sa.Integer(), nullable=False),
        # These have to be nullable so we can do the type conversion
        sa.Column('master_event_id', sa.Integer(), nullable=True),
        sa.Column('master_event_uid', sa.String(
            length=767, collation='ascii_general_ci'), nullable=True),
        sa.Column('original_start_time', sa.DateTime(), nullable=True),
        sa.Column('cancelled', sa.Boolean(), default=False),
        sa.ForeignKeyConstraint(['id'], ['event.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['master_event_id'], ['event.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'recurringevent',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rrule', sa.String(length=255), nullable=True),
        sa.Column('exdate', sa.Text(), nullable=True),
        sa.Column('until', sa.DateTime(), nullable=True),
        sa.Column('start_timezone', sa.String(35), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['event.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.add_column(u'event', sa.Column('type', sa.String(length=30),
                  nullable=True))
    op.create_index('ix_recurringeventoverride_master_event_uid',
                    'recurringeventoverride', ['master_event_uid'],
                    unique=False)
    op.alter_column(u'event', 'recurrence', type_=sa.Text())


def downgrade():
    op.drop_column(u'event', 'type')
    op.drop_table('recurringevent')
    op.drop_table('recurringeventoverride')


def populate():
    # Populate new classes from the existing data
    from inbox.models.event import (Event, RecurringEvent,
                                    RecurringEventOverride)
    from inbox.models.session import session_scope
    from inbox.events.util import parse_datetime
    from inbox.events.recurring import link_events

    with session_scope() as db:
        # Redo recurrence rule population, since we extended the column length
        print "Repopulating max-length recurrences...",
        for e in db.query(Event).filter(
                sa.func.length(Event.recurrence) > 250):
            try:
                raw_data = json.loads(e.raw_data)
            except:
                try:
                    raw_data = ast.literal_eval(e.raw_data)
                except:
                    print "Could not load raw data for event {}".format(e.id)
                    continue
            e.recurrence = raw_data['recurrence']
        db.commit()
        print "done."

        print "Updating types for Override...",
        # Slightly hacky way to convert types (only needed for one-off import)
        convert = """UPDATE event SET type='recurringeventoverride' WHERE
                     raw_data LIKE '%recurringEventId%'"""
        db.execute(convert)
        create = """INSERT INTO recurringeventoverride (id)
                    SELECT id FROM event
                    WHERE type='recurringeventoverride'
                    AND id NOT IN
                    (SELECT id FROM recurringeventoverride)"""
        try:
            db.execute(create)
        except Exception as e:
            print "Couldn't insert RecurringEventOverrides: {}".format(e)
            exit(2)
        print "done."

        c = 0
        print "Expanding Overrides .",
        query = db.query(RecurringEventOverride)
        for e in query:
            try:
                # Some raw data is str(dict), other is json.dumps
                raw_data = json.loads(e.raw_data)
            except:
                try:
                    raw_data = ast.literal_eval(e.raw_data)
                except:
                    print "Could not load raw data for event {}".format(e.id)
                    continue
            rec_uid = raw_data.get('recurringEventId')
            if rec_uid:
                e.master_event_uid = rec_uid
                ost = raw_data.get('originalStartTime')
                if ost:
                    # this is a dictionary with one value
                    start_time = ost.values().pop()
                    e.original_start_time = parse_datetime(start_time)
                # attempt to get the ID for the event, if we can, and
                # set the relationship appropriately
                if raw_data.get('status') == 'cancelled':
                    e.cancelled = True
                link_events(db, e)
                c += 1
                if c % 100 == 0:
                    print ".",
                    sys.stdout.flush()
        db.commit()
        print "done. ({} modified)".format(c)

        # Convert Event to RecurringEvent
        print "Updating types for RecurringEvent...",
        convert = """UPDATE event SET type='recurringevent' WHERE
                     recurrence IS NOT NULL"""
        db.execute(convert)
        create = """INSERT INTO recurringevent (id)
                    SELECT id FROM event
                    WHERE type='recurringevent'
                    AND id NOT IN
                    (SELECT id FROM recurringevent)"""
        try:
            db.execute(create)
        except Exception as e:
            print "Couldn't insert RecurringEvents: {}".format(e)
            exit(2)
        print "done."

        # Pull out recurrence metadata from recurrence
        c = 0
        print "Expanding master events .",
        query = db.query(RecurringEvent)
        for r in query:
            r.unwrap_rrule()
            try:
                raw_data = json.loads(r.raw_data)
            except:
                try:
                    raw_data = ast.literal_eval(e.raw_data)
                except:
                    print "Could not load raw data for event {}".format(r.id)
                    continue
            r.start_timezone = raw_data['start'].get('timeZone')
            # find any un-found overrides that didn't have masters earlier
            link_events(db, r)
            db.add(r)
            c += 1
            if c % 100 == 0:
                print ".",
                sys.stdout.flush()
        db.commit()
        print "done. ({} modified)".format(c)

        # Finally, convert all remaining Events to type='event'
        convert = """UPDATE event SET type='event' WHERE type IS NULL"""
        db.execute(convert)


if __name__ == "__main__":
    populate()
