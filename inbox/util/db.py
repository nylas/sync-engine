from sqlalchemy.engine import reflection
from sqlalchemy.schema import MetaData, Table, ForeignKeyConstraint
from sqlalchemy.schema import DropTable, DropConstraint

# http://www.sqlalchemy.org/trac/wiki/UsageRecipes/DropEverything
def drop_everything(engine, with_users=False):
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
        if not with_users and table_name == 'user':
            continue
        fks = []
        for fk in inspector.get_foreign_keys(table_name):
            if not fk['name']:
                continue
            fks.append(
                ForeignKeyConstraint((),(),name=fk['name'])
                )
        t = Table(table_name,metadata,*fks)
        tbs.append(t)
        all_fks.extend(fks)

    for fkc in all_fks:
        conn.execute(DropConstraint(fkc))

    for table in tbs:
        conn.execute(DropTable(table))

    trans.commit()
