from __future__ import with_statement
import sys
from logging.config import fileConfig

from alembic import context

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
alembic_config = context.config
# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(alembic_config.config_file_name)

# Pick what db to run migrations against.
# Default is dev; if alembic was invoked with --tag=test or --tag=prod,
# load those configs instead.
env = context.get_tag_argument() or 'dev'

# Load config before anything
from inbox.config import load_config
config = load_config(env)

if env == 'test':
    if not config.get_required('MYSQL_HOSTNAME') == 'localhost':
        sys.exit('Tests should only be run on localhost DB!')
elif env == 'prod':
    print 'Running migrations against prod database'

# Add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
from inbox.models.base import MailSyncBase
target_metadata = MailSyncBase.metadata

from inbox.ignition import main_engine

# Other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option('my_important_option')
# ... etc.


def run_migrations_offline():
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(engine=main_engine(pool_size=1, max_overflow=0))

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    engine = main_engine(pool_size=1, max_overflow=0)

    connection = engine.connect()
    context.configure(
        connection=connection,
        target_metadata=target_metadata
    )

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
