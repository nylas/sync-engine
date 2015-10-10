import subprocess


def setup_test_db():
    """
    Creates a new, empty test database with table structure generated
    from declarative model classes; returns an engine for that database.

    """
    from inbox.config import config
    from inbox.ignition import engine_manager
    from inbox.ignition import init_db

    # Hardcode this part instead of reading from config because the idea of a
    # general-purpose 'DROP DATABASE' function is unsettling
    for name in ('test', 'test_1'):
        cmd = 'DROP DATABASE IF EXISTS {name}; ' \
              'CREATE DATABASE IF NOT EXISTS {name} ' \
              'DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE ' \
              'utf8mb4_general_ci'.format(name=name)

        subprocess.check_call('mysql -uinboxtest -pinboxtest '
                              '-e "{}"'.format(cmd), shell=True)

    database_params = config.get_required('DATABASES')
    for key in sorted(database_params):
        engine = engine_manager.engines[int(key)]
        init_db(engine, int(key))
