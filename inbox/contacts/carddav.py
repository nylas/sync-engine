"""
This is a Python module for working with the iCloud CardDav implementation
based on .

Note that this will only download up to 5000 contacts+groups. To download more,
this implementation should be changed to WebDAV Sync
).

References:
- CardDav: https://tools.ietf.org/html/rfc6352
- http://sabre.io/dav/building-a-carddav-client/
- https://github.com/schmurfy/dav4rack_ext/blob/master/lib/
        dav4rack_ext/carddav/controller.rb
- WebDav Sync: http://tools.ietf.org/html/rfc6578

TODOs

- Implement WebDavSync
- Support manipulating groups: http://stackoverflow.com/q/24202551

"""

import requests
import lxml.etree as ET


# Fake it till you make it
USER_AGENT = "User-Agent: DAVKit/4.0.1 (730); CalendarStore/4.0.1 " + \
    "(973); iCal/4.0.1 (1374); Mac OS X/10.6.2 (10C540)"


def supports_carddav(url):
    """ Basic verification that the endpoint supports CardDav
    """
    response = requests.request(
        'OPTIONS', url,
        headers={'User-Agent': USER_AGENT,
                 'Depth': '1'})
    response.raise_for_status()   # if not 2XX status
    if 'addressbook' not in response.headers.get('DAV', ''):
        raise Exception("URL is not a CardDAV resource")


class CardDav(object):
    """ NOTE: Only supports iCloud for now """

    def __init__(self, email_address, password, base_url):
        self.session = requests.Session()
        self.session.auth = (email_address, password)
        self.session.verify = True  # verify SSL certs
        self.session.headers.update({'User-Agent': USER_AGENT,
                                     'Depth': '1'})
        self.base_url = base_url

    def get_principal_url(self):
        """ Use PROPFIND method to find the `principal` carddav url """

        payload = """
            <A:propfind xmlns:A='DAV:'>
                <A:prop>
                    <A:current-user-principal/>
                </A:prop>
            </A:propfind>
        """
        response = self.session.request('PROPFIND',
                                        self.base_url,
                                        data=payload)
        response.raise_for_status()

        xml = response.content
        element = ET.XML(xml)
        principal_href = element[0][1][0][0][0].text
        return principal_href

    def get_address_book_home(self, url):
        payload = """
        <D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:carddav">
          <D:prop>
            <D:getetag/>
            <C:addressbook-home-set/>
            <C:principal-address/>
            <D:displayname/>
          </D:prop>
        </D:propfind>
        """

        response = self.session.request('PROPFIND',
                                        url,
                                        data=payload)
        response.raise_for_status()
        xml = response.content
        element = ET.XML(xml)
        address_book_home = element[0][1][0][0][0].text
        return address_book_home

    # This is used to find the different addressbooks, but because we
    # are dealing with iCloud, we know there is only one at `card/`
    # def get_address_book_meta(self, url):
    #     payload = """
    #     <d:propfind xmlns:d="DAV:" xmlns:cs="http://calendarserver.org/ns/">
    #       <d:prop>
    #          <d:resourcetype />
    #          <d:displayname />
    #          <cs:getctag />
    #          <d:addressbook-description/>
    #       </d:prop>
    #     </d:propfind>
    #     """
    #     response = self.session.request('PROPFIND',
    #                                     url,
    #                                     data=payload)
    #     response.raise_for_status()
    #     return response.content

    def get_cards(self, url):
        payload = """
       <C:addressbook-query xmlns:D="DAV:"
                         xmlns:C="urn:ietf:params:xml:ns:carddav">
         <D:prop>
           <D:getetag/>
           <C:address-data content-type="application/vcard+xml" version="4.0"/>
         </D:prop>
         <C:filter/>
       </C:addressbook-query>
        """

        response = self.session.request('REPORT',
                                        url,
                                        data=payload,)

        response.raise_for_status()
        return response.content


#####################################################


# FOR MODIFICATIONS

# def update_vcard(self, card, href, etag):
#     """
#     pushes changed vcard to the server
#     card: vcard as unicode string
#     etag: str or None, if this is set to a string, card is only updated if
#           remote etag matches. If etag = None the update is forced anyway
#      """
#      # TODO what happens if etag does not match?
#     self._check_write_support()
#     remotepath = str(self.url.base + href)
#     headers = self.headers
#     headers['content-type'] = 'text/vcard'
#     if etag is not None:
#         headers['If-Match'] = etag
#     self.session.put(remotepath, data=card, headers=headers,
#                      **self._settings)


# def delete_vcard(self, href, etag):
#     """deletes vcard from server

#     deletes the resource at href if etag matches,
#     if etag=None delete anyway
#     :param href: href of card to be deleted
#     :type href: str()
#     :param etag: etag of that card, if None card is always deleted
#     :type href: str()
#     :returns: nothing
#     """
#     # TODO: what happens if etag does not match, url does not exist etc ?
#     self._check_write_support()
#     remotepath = str(self.url.base + href)
#     headers = self.headers
#     headers['content-type'] = 'text/vcard'
#     if etag is not None:
#         headers['If-Match'] = etag
#     response = self.session.delete(remotepath,
#                                    headers=headers,
#                                    **self._settings)
#     response.raise_for_status()


# def upload_new_card(self, card):
#     """
#     upload new card to the server

#     :param card: vcard to be uploaded
#     :type card: unicode
#     :rtype: tuple of string (path of the vcard on the server) and etag of
#             new card (string or None)
#     """
#     self._check_write_support()
#     card = card.encode('utf-8')
#     for _ in range(0, 5):
#         rand_string = get_random_href()
#         remotepath = str(self.url.resource + rand_string + ".vcf")
#         headers = self.headers
#         headers['content-type'] = 'text/vcard'  # TODO perhaps this should
#         # be set to the value this carddav server uses itself
#         headers['If-None-Match'] = '*'
#         response = requests.put(remotepath, data=card, headers=headers,
#                                 **self._settings)
#         if response.ok:
#             parsed_url = urlparse.urlparse(remotepath)
#             if 'etag' not in response.headers.keys() or \
#                   response.headers['etag'] is None:
#                 etag = ''
#             else:
#                 etag = response.headers['etag']

#             return (parsed_url.path, etag)
#     response.raise_for_status()
