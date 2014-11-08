#!/usr/bin/env python
import click

from inbox.search.util import delete_namespace_index as delete_index


@click.command()
@click.option('--namespace_public_id', default=None)
def delete_namespace_index(namespace_public_id):
    """
    Delete an Elasticsearch index for a namespace. All namespace indexes are
    deleted by default, use `namespace_public_id` to specify only one.

    """
    delete_index(namespace_public_id)


if __name__ == '__main__':
    delete_namespace_index()
