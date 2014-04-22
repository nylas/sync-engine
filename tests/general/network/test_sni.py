""" Ensure that our `requests` module has SNI support. """

import requests


def test_requests_sni():
    for host in ['alice', 'bob', 'carol', 'dave', 'mallory', 'www']:
        response = requests.get('https://{}.sni.velox.ch'.format(host))
        html = response.content.decode('utf-8', 'replace')
        assert 'Great!' in html, host
