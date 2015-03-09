"""Provide iCloud contacts"""

from inbox.log import get_logger
logger = get_logger()

from carddav import CardDav
import lxml.etree as ET
from inbox.contacts.vcard import vcard_from_string
from inbox.contacts.carddav import supports_carddav

from inbox.models.session import session_scope
from inbox.models import Contact
from inbox.models.backends.generic import GenericAccount


ICLOUD_CONTACTS_URL = 'https://contacts.icloud.com/'


class ICloudContactsProvider(object):
    """
    Base class to fetch and parse iCloud contacts
    """

    PROVIDER_NAME = 'icloud'

    def __init__(self, account_id, namespace_id):
        supports_carddav(ICLOUD_CONTACTS_URL)
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.log = logger.new(account_id=account_id, component='contacts sync',
                              provider=self.PROVIDER_NAME)

    def _vCard_raw_to_contact(self, cardstring):
        card = vcard_from_string(cardstring)

        def _x(key):  # Ugly parsing helper for ugly formats
            if key in card:
                try:
                    return card[key][0][0]
                except IndexError:
                    pass

        # Skip contact groups for now
        if _x('X-ADDRESSBOOKSERVER-KIND') == 'group':
            return None

        uid = _x('UID')
        name = _x('FN')
        email_address = _x('EMAIL')
        # TODO add these later
        # street_address = _x('ADR')
        # phone_number = _x('TEL')
        # organization = _x('ORG')

        return Contact(namespace_id=self.namespace_id,
                       provider_name=self.PROVIDER_NAME,
                       source='remote',
                       uid=uid,
                       name=name,
                       email_address=email_address,
                       raw_data=cardstring)

    def get_items(self, sync_from_dt=None, max_results=100000):
        with session_scope() as db_session:
            account = db_session.query(GenericAccount).get(self.account_id)
            email_address = account.email_address
            password = account.password
            if account.provider != 'icloud':
                self.log.error("Can't sync contacts for non iCloud provider",
                               account_id=account.id,
                               provider=account.provider)
                return []

        c = CardDav(email_address, password, ICLOUD_CONTACTS_URL)

        # Get the `principal` URL for the users's CardDav endpont
        principal = c.get_principal_url()

        # Get addressbook home URL on user's specific iCloud shard/subdomain
        home_url = c.get_address_book_home(ICLOUD_CONTACTS_URL + principal)
        self.log.info("Home URL for user's contacts: {}".format(home_url))
        self.log.debug("Requesting cards for user")

        # This request is limited to returning 5000 items
        returned_cards = c.get_cards(home_url + 'card/')

        root = ET.XML(returned_cards)

        all_contacts = []
        for refprop in root.iterchildren():

            try:
                cardstring = refprop[1][0][1].text
            except IndexError:
                # This can happen when there are errors or other responses.
                # Currently if there are over 5000 contacts, it trigger the
                # response number-of-matches-within-limits
                # TODO add paging for requesting all
                self.log.error("Error parsing CardDav response into contact: "
                               "{}".format(ET.tostring(refprop)))
                continue

            new_contact = self._vCard_raw_to_contact(cardstring)
            if new_contact:
                all_contacts.append(new_contact)

        self.log.info("Saving {} contacts from iCloud sync"
                      .format(len(all_contacts)))
        return all_contacts
