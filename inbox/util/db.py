from sqlalchemy.engine import reflection
from sqlalchemy.schema import MetaData, Table, ForeignKeyConstraint
from sqlalchemy.schema import DropTable, DropConstraint


# http://www.sqlalchemy.org/trac/wiki/UsageRecipes/DropEverything
def drop_everything(engine, keep_tables=[], reset_columns={}):
    """ Drops all tables in the db unless their name is in `keep_tables`.
        `reset_columns` is used to specify the columns that should be reset to
        default value in the tables that we're keeping -
        provided as a dict of table_name: list_of_column_names.
    """

    conn = engine.connect()
    trans = conn.begin()

    inspector = reflection.Inspector.from_engine(engine)

    # gather all data first before dropping anything.
    # some DBs lock after things have been dropped in
    # a transaction.

    metadata = MetaData()

    tbs = []
    all_fks = []

    for table_name in inspector.get_table_names():
        if table_name in keep_tables:
            # Reset certain columns in certain tables we're keeping
            if table_name in reset_columns:
                t = Table(table_name, metadata)

                column_names = reset_columns[table_name]
                for c in inspector.get_columns(table_name):
                    if c['name'] in column_names:
                        assert c['default']

                        q = "UPDATE {0} SET {1}={2};".\
                            format(table_name, c['name'], c['default'])
                        conn.execute(q)
            continue

        fks = []
        for fk in inspector.get_foreign_keys(table_name):
            if not fk['name']:
                continue
            fks.append(ForeignKeyConstraint((), (), name=fk['name']))
        t = Table(table_name, metadata, *fks)
        tbs.append(t)
        all_fks.extend(fks)

    for fkc in all_fks:
        conn.execute(DropConstraint(fkc))

    for table in tbs:
        conn.execute(DropTable(table))

    trans.commit()
