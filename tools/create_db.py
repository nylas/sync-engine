import os
import sqlalchemy
from alembic.config import Config as alembic_config
from alembic import command as alembic_command


basic_db_uri = 'mysql://root:root@localhost'
engine = sqlalchemy.create_engine(basic_db_uri) # connect to server

print 'Creating database: test'
engine.execute("CREATE DATABASE IF NOT EXISTS test DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_general_ci") #create db
engine.execute("GRANT ALL PRIVILEGES ON test.* TO inboxtest@localhost IDENTIFIED BY 'inboxtest'") #create db

print 'Creating database: inbox'
engine.execute("CREATE DATABASE IF NOT EXISTS inbox DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_general_ci;")
engine.execute("GRANT ALL PRIVILEGES ON inbox.* TO inbox@localhost IDENTIFIED BY 'inbox'")


# Stamp initial alembic revision
inbox_db_engine = sqlalchemy.create_engine('{uri}/{database}'.format(uri=basic_db_uri, database='inbox'))

if engine.dialect.has_table(inbox_db_engine, "alembic_version"):
	res = inbox_db_engine.execute("SELECT version_num from alembic_version")
	current_revision = [r for r in res][0][0]
	assert current_revision, "Need current revision in alembic_version table..."
	print 'Already revisioned by alembic %s' % current_revision
else:
	alembic_ini_filename = 'alembic.ini'  # top-level, with setup.sh
	assert os.path.isfile(alembic_ini_filename), "Must have alembic.ini file at %s" % alembic_ini_filename
	alembic_cfg = alembic_config(alembic_ini_filename)

	print 'Stamping with alembic revision'
	alembic_command.stamp(alembic_cfg, "head")


print 'Finished setting up database'