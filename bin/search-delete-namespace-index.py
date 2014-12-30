#!/usr/bin/env python
import click

from inbox.search.util import delete_namespace_indexes as delete_indexes


@click.command()
@click.option('--namespace_ids', default=None)
def delete_namespace_indexes(namespace_ids):
    """
    Delete the Elasticsearch indexes for a list of namespaces, specified by id.
    If namespace_ids=None, all namespace indexes are deleted (the default).

    """
    delete_indexes(namespace_ids)


if __name__ == '__main__':
    delete_namespace_indexes()
