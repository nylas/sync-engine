import subprocess


def create_test_db():
    """ Creates new, empty test databases. """
    from inbox.config import config

    database_hosts = config.get_required('DATABASE_HOSTS')
    schemas = [shard['SCHEMA_NAME'] for host in database_hosts for
               shard in host['SHARDS']]
    # The various test databases necessarily have "test" in their name.
    assert all(['test' in s for s in schemas])

    for name in schemas:
        cmd = 'DROP DATABASE IF EXISTS {name}; ' \
              'CREATE DATABASE IF NOT EXISTS {name} ' \
              'DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE ' \
              'utf8mb4_general_ci'.format(name=name)

        subprocess.check_call('mysql -uinboxtest -pinboxtest '
                              '-e "{}"'.format(cmd), shell=True)


def setup_test_db():
    """
    Creates new, empty test databases with table structures generated
    from declarative model classes.

    """
    from inbox.config import config
    from inbox.ignition import engine_manager
    from inbox.ignition import init_db

    create_test_db()

    database_hosts = config.get_required('DATABASE_HOSTS')
    for host in database_hosts:
        for shard in host['SHARDS']:
            key = shard['ID']
            engine = engine_manager.engines[key]
            init_db(engine, key)
