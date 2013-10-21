import dns.resolver

from urllib import urlencode

import tornado.httpclient
from tornado import escape



def validate_email(address_text):

    args = {
        "address": address_text
        }

    MAILGUN_API_PUBLIC_KEY = "pubkey-8nre-3dq2qn8-jjopmq9wiwu4pk480p2"
    MAILGUN_VALIDATE_API_URL = "https://api.mailgun.net/v2/address/validate?" + urlencode(args)


    request = tornado.httpclient.HTTPRequest(MAILGUN_VALIDATE_API_URL)
    request.auth_username = 'api'
    request.auth_password = MAILGUN_API_PUBLIC_KEY

    try:
        sync_client = tornado.httpclient.HTTPClient()  # Todo make async?
        response = sync_client.fetch(request)
    except tornado.httpclient.HTTPError, e:
        response = e.response
        pass  # handle below
    except Exception, e:
        log.error(e)
        raise tornado.web.HTTPError(500, "Internal email validation error.")
    if response.error:
        error_dict = escape.json_decode(response.body)
        log.error(error_dict)
        raise tornado.web.HTTPError(500, "Internal email validation error.")

    body = escape.json_decode(response.body)

    is_valid = body['is_valid']
    if is_valid:
        # Must have Gmail or Google Apps MX records
        domain = body['parts']['domain']
        answers = dns.resolver.query(domain, 'MX')

        gmail_mx_servers = [
                # Google apps for your domain
                'aspmx.l.google.com.',
                'aspmx2.googlemail.com.',
                'aspmx3.googlemail.com.',
                'aspmx4.googlemail.com.',
                'aspmx5.googlemail.com.',
                'alt1.aspmx.l.google.com.',
                'alt2.aspmx.l.google.com.',
                'alt3.aspmx.l.google.com.',
                'alt4.aspmx.l.google.com.',

                # Gmail
                'gmail-smtp-in.l.google.com.',
                'alt1.gmail-smtp-in.l.google.com.',
                'alt2.gmail-smtp-in.l.google.com.',
                'alt3.gmail-smtp-in.l.google.com.',
                'alt4.gmail-smtp-in.l.google.com.'
                 ]

        # All relay servers must be gmail
        for rdata in answers:
            if not str(rdata.exchange).lower() in gmail_mx_servers:
                is_valid = False
                log.error("Non-Google MX record: %s" % str(rdata.exchange))


    return dict(
        valid_for_inbox = is_valid,
        did_you_mean = body['did_you_mean'],
        valid_address = body['address']
    )

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
