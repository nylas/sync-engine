#!/bin/sh

set -e

# see setup.sh for info
color() { printf '\033[%sm%s\033[m\n' "$@"; }

color '36;1' "Loading previous test data..."
mysql -uroot -proot -Dtest < tests/data/base_dump.sql

color '36;1' "Applying revisions..."
alembic upgrade head --tag=test

color '36;1' "Dumping test data..."
mysqldump -uroot -proot test > tests/data/base_dump.sql

color '32;1' "Test DB updated successfully."
