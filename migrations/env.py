from __future__ import with_statement
import json
import sys
import os
from alembic import context

from logging.config import fileConfig

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
alembic_config = context.config
# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(alembic_config.config_file_name)

# If alembic was invoked with --tag=test, override these main config values
if context.get_tag_argument() == 'test':
    from inbox.config import config
    root_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
    config_path = os.path.join(root_path, 'etc', "config-%s.json" % 'test')
    with open(config_path) as f:
        config.update(json.load(f))
        if not config.get('MYSQL_HOSTNAME') == "localhost":
            sys.exit("Tests should only be run on localhost DB!")


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
from inbox.models.base import MailSyncBase
target_metadata = MailSyncBase.metadata

from inbox.ignition import main_engine

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

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
    """Run migrations in 'online' mode.

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
