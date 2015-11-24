import re
import json

import boto3

from flanker.addresslib import address

from inbox.config import config
from inbox.models import Contact
from inbox.models.session import session_scope
from inbox.sqlalchemy_ext.util import safer_yield_per

from sqlalchemy.orm import joinedload

from nylas.logging import get_logger
log = get_logger()

# CloudSearch charges per 1000 batched uploads. Batches must be
# < 5 MB. This assumes that individual items are <= 1kb each.
DOC_UPLOAD_CHUNK_SIZE = 5000

# Be explicit about which fields we search by default.
SEARCH_OPTIONS = '{"fields": ["name", "phone_numbers", "email_address"]}'
search_service_url = config.get('SEARCH_SERVICE_ENDPOINT')
doc_service_url = config.get('DOCUMENT_SERVICE_ENDPOINT')


def get_domain_config(conn, domain_name):
    domains = conn.describe_domains()

    for d in domains['DomainStatusList']:
        if d['DomainName'] == domain_name:
            return d
    return None


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


# CloudSearch doesn't like these characters (reasonably so!)
non_printable_chars_regex = re.compile(
    '[\x01\x02\x03\x04\x05\x06\x07\x08'
    '\x0b\x0e\x10\x11\x15\x17\x19'
    '\x1a\x1b\x1c\x1d\x1e\x1f]')


def cloudsearch_contact_repr(contact):
    # strip display name out of email address
    parsed = address.parse(contact.email_address)
    name = contact.name or ''
    email_address = parsed.address if parsed else ''
    name_contains_bad_codepoints = re.search(
        non_printable_chars_regex, contact.name or '')
    email_contains_bad_codepoints = re.search(
        non_printable_chars_regex, email_address)
    if name_contains_bad_codepoints or email_contains_bad_codepoints:
        log.warning("bad codepoint in contact", contact_id=contact.id,
                    name=contact.name, email_address=email_address)
        name = non_printable_chars_regex.sub('', name)
        email_address = non_printable_chars_regex.sub('', email_address)
    return {
        'id': contact.id,
        'namespace_id': contact.namespace_id,
        'name': name,
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
        # see http://docs.aws.amazon.com/cloudsearch/latest/developerguide/paginating-results.html#deep-paging # noqa
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
        if search_service_url and doc_service_url:
            result_ids = self.fetch_matching_ids_page(
                query=search_query, start=offset, size=limit)
            log.info('received result IDs', result_ids=result_ids)

            if result_ids:
                return db_session.query(Contact).filter(
                    Contact.namespace_id == self.namespace_id,
                    Contact.id.in_(result_ids)).options(
                        joinedload("phone_numbers")).all()
            else:
                return []
        else:
            log.warning('cloudsearch not configured; returning no results')
            return []


def index_namespace(namespace_id):
    if not search_service_url or not doc_service_url:
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
        with session_scope(namespace_id) as db_session:
            query = db_session.query(Contact).options(
                joinedload("phone_numbers")).filter_by(
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
    if not search_service_url or not doc_service_url:
        raise Exception('CloudSearch not configured; cannot update index')
    else:
        doc_service = get_doc_service()

        for namespace_id in namespace_ids:
            search_client = ContactSearchClient(namespace_id)

            record_ids = search_client.fetch_all_matching_ids()

            log.info("deleting all record_ids",
                     namespace_id=namespace_id,
                     total=len(record_ids),
                     ids=record_ids)

            # Keep upload under 5 MB if each delete doc is about 265 bytes.
            chunk_size = 18000

            docs = []
            for id_ in record_ids:
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
