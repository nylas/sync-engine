from __future__ import with_statement
from alembic import context

from logging.config import fileConfig

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(context.config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
from inbox.models.base import MailSyncBase
target_metadata = MailSyncBase.metadata

from inbox.config import config
from inbox.ignition import EngineManager


# Alembic configuration is confusing. Here we look for a shard id both as a
# "main option" (where it's programmatically set by bin/create-db), and in the
# "x" argument, which is the primary facility for passing additional
# command-line args to alembic. So you would do e.g.
#
# alembic -x shard_id=1 upgrade +1
#
# to target shard 1 for the migration.
config_shard_id = context.config.get_main_option('shard_id')
x_shard_id = context.get_x_argument(as_dictionary=True).get(
    'shard_id')

if config_shard_id is not None:
    shard_id = int(config_shard_id)
elif x_shard_id is not None:
    shard_id = int(x_shard_id)
else:
    raise ValueError('No shard_id is configured for migration; '
                     'run `alembic -x shard_id=<target shard id> upgrade +1`')


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    engine_manager = EngineManager(config.get_required('DATABASE_HOSTS'),
                                   config.get_required('DATABASE_USERS'),
                                   include_disabled=True)
    context.configure(engine=engine_manager.engines[shard_id])

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    engine_manager = EngineManager(config.get_required('DATABASE_HOSTS'),
                                   config.get_required('DATABASE_USERS'),
                                   include_disabled=True)

    engine = engine_manager.engines[shard_id]
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
