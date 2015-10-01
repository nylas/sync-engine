import re
import json

import boto3

from flanker.addresslib import address

from inbox.config import config
from inbox.models import Contact
from inbox.models.session import session_scope
from inbox.sqlalchemy_ext.util import safer_yield_per

from nylas.logging import get_logger
log = get_logger()

CLOUDSEARCH_DOMAIN = config.get('CLOUDSEARCH_DOMAIN')

# CloudSearch charges per 1000 batched uploads. Batches must be
# < 5 MB. This assumes that individual items are <= 1kb each.
DOC_UPLOAD_CHUNK_SIZE = 5000

# Be explicit about which fields we search by default.
SEARCH_OPTIONS = '{"fields": ["name", "phone_numbers", "email_address"]}'


def get_domain_config(conn, domain_name):
    domains = conn.describe_domains()

    for d in domains['DomainStatusList']:
        if d['DomainName'] == domain_name:
            return d
    return None


def get_service_urls():
    conn = boto3.client(
        'cloudsearch', region_name="us-west-2",
        aws_access_key_id=config.get_required('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=config.get_required('AWS_SECRET_ACCESS_KEY'))
    domain_config = get_domain_config(conn, CLOUDSEARCH_DOMAIN)
    search_service_url = domain_config['SearchService']['Endpoint']
    doc_service_url = domain_config['DocService']['Endpoint']
    return (search_service_url, doc_service_url)


# Discover service endpoints on module import
if CLOUDSEARCH_DOMAIN:
    # boto installs retry handlers that retry any requests on timeouts or
    # other failures
    search_service_url, doc_service_url = get_service_urls()


def get_search_service():
    return boto3.client(
        "cloudsearchdomain", region_name="us-west-2",
        aws_access_key_id=config.get_required('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=config.get_required('AWS_SECRET_ACCESS_KEY'),
        endpoint_url='https://{0}'.format(search_service_url))


def get_doc_service():
    return boto3.client(
        "cloudsearchdomain", region_name="us-west-2",
        aws_access_key_id=config.get_required('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=config.get_required('AWS_SECRET_ACCESS_KEY'),
        endpoint_url='https://{0}'.format(doc_service_url))


def _strip_non_numeric(phone_number):
    digits = [ch for ch in phone_number if re.match('[0-9]', ch)]
    return ''.join(digits)


def cloudsearch_contact_repr(contact):
    # strip display name out of email address
    parsed = address.parse(contact.email_address)
    email_address = parsed.address if parsed else ''
    return {
        'id': contact.id,
        'namespace_id': contact.namespace_id,
        'name': contact.name or '',
        'email_address': email_address,
        'phone_numbers': [_strip_non_numeric(p.number)
                          for p in contact.phone_numbers]
    }


class ContactSearchClient(object):
    """ Search client that talks to AWS CloudSearch (or a compatible API). """

    def __init__(self, namespace_id):
        self.namespace_id = namespace_id
        self.search_service = get_search_service()

    def _fetch_search_page(self, **kwargs):
        """ Make sure we always filter results by namespace and apply the
        correct query options. """

        namespace_filter = '(and namespace_id:{})'.format(self.namespace_id)
        if 'query' not in kwargs:
            kwargs['query'] = namespace_filter
            kwargs['queryParser'] = 'structured'
        else:
            kwargs['filterQuery'] = namespace_filter
            kwargs['queryParser'] = 'simple'
        kwargs['queryOptions'] = SEARCH_OPTIONS

        return self.search_service.search(**kwargs)

    def _ids_from_results(self, results):
        return [long(hit['id']) for hit in results['hits']['hit']]

    def fetch_matching_ids_page(self, **kwargs):
        """ Fetch a single page of search result IDs.

        Specify the query with 'query'.

        You can control the size of the page with the 'size' parameter, up
        to a limit of 10000. The 'start' parameter determines the offset from
        0 where the results page starts.

        """
        results = self._fetch_search_page(**kwargs)
        return self._ids_from_results(results)

    def fetch_all_matching_ids(self):
        """ Fetches *all* match IDs, even if there are tens of thousands. """
        # see http://docs.aws.amazon.com/cloudsearch/latest/developerguide/paginating-results.html#deep-paging
        #
        # boto limited page size to 500; not sure what boto3's limit is.
        # If higher, consider cranking up quite a bit since only IDs are
        # returned.
        kwargs = {'cursor': 'initial', 'size': 500}

        results = self._fetch_search_page(**kwargs)
        result_ids = self._ids_from_results(results)

        # If there are more results to fetch, fetch them.
        while ('cursor' in results['hits'] and
                len(result_ids) < int(results['hits']['found'])):
            log.info("fetching next page")
            kwargs['cursor'] = results['hits']['cursor']
            results = self._fetch_search_page(**kwargs)
            result_ids.extend(self._ids_from_results(results))

        return result_ids

    # Note that our API constrains 'limit' to a max of 1000, which is safe to
    # pass through to cloudsearch.
    def search_contacts(self, db_session, search_query, offset=0, limit=40):
        if CLOUDSEARCH_DOMAIN:
            result_ids = self.fetch_matching_ids_page(
                query=search_query, start=offset, size=limit)
            log.info('received result IDs', result_ids=result_ids)

            if result_ids:
                return db_session.query(Contact).filter(
                    Contact.namespace_id == self.namespace_id,
                    Contact.id.in_(result_ids)).all()
            else:
                return []
        else:
            log.warning('cloudsearch not configured; returning no results')
            return []


def index_namespace(namespace_id):
    if not CLOUDSEARCH_DOMAIN:
        raise Exception('CloudSearch not configured; cannot index')
    else:
        search_client = ContactSearchClient(namespace_id)
        doc_service = get_doc_service()

        # Look up previously indexed data so we can delete any records which
        # have disappeared.
        #
        previous_records = search_client.fetch_all_matching_ids()

        log.info("previous records", total=len(previous_records),
                 ids=previous_records)

        indexed = 0
        current_records = set()
        docs = []
        with session_scope() as db_session:
            query = db_session.query(Contact).filter_by(
                    namespace_id=namespace_id)
            for contact in safer_yield_per(query, Contact.id, 0, 1000):
                log.info("indexing", contact_id=contact.id)
                current_records.add(long(contact.id))
                contact_object = cloudsearch_contact_repr(contact)
                docs.append({'type': 'add', 'id': contact.id,
                             'fields': contact_object})
                if len(docs) > DOC_UPLOAD_CHUNK_SIZE:
                    doc_service.upload_documents(
                        documents=json.dumps(docs),
                        contentType='application/json')
                    indexed += len(docs)
                    docs = []

        indexed += len(docs)

        # Deletes are small, so we can stick 'em on this batch.
        deleted_records = set(previous_records).difference(current_records)
        for id_ in deleted_records:
            log.info("deleting", contact_id=id_)
            docs.append({'type': 'delete', 'id': id_})

        if docs:
            doc_service.upload_documents(
                documents=json.dumps(docs),
                contentType='application/json')

        log.info("namespace index complete",
                 total_contacts_indexed=indexed,
                 total_contacts_deleted=len(deleted_records))


def delete_namespace_indexes(namespace_ids):
    if not CLOUDSEARCH_DOMAIN:
        raise Exception('CloudSearch not configured; cannot update index')
    else:
        doc_service = get_doc_service()

        for namespace_id in namespace_ids:
            search_client = ContactSearchClient(namespace_id)

            previous_records = search_client.fetch_all_matching_ids()

            log.info("deleting all records",
                     namespace_id=namespace_id,
                     total=len(previous_records),
                     ids=previous_records)

            # Keep upload under 5 MB if each delete doc is about 265 bytes.
            chunk_size = 18000

            docs = []
            for id_ in previous_records:
                docs.append({'type': 'delete', 'id': id_})

                if len(docs) > chunk_size:
                    doc_service.upload_documents(
                        documents=json.dumps(docs),
                        contentType='application/json')
                    docs = []

            if docs:
                doc_service.upload_documents(
                    documents=json.dumps(docs),
                    contentType='application/json')
