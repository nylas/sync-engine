#!/usr/bin/env python
import click

from inbox.search.util import delete_namespace_indexes as delete_indexes


@click.command()
@click.argument('namespace_ids')
def delete_namespace_indexes(namespace_ids):
    """
    Delete the Elasticsearch indexes for a list of namespaces, specified by id.

    """
    delete_indexes(namespace_ids)


if __name__ == '__main__':
    delete_namespace_indexes()
