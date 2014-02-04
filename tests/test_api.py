import json
from bson import json_util

# pytest fixtures outside of conftest.py must be imported for discovery
from .util.api import api_client

USER_ID = 1
NAMESPACE_ID = 1

def test_is_mailing_list_message(api_client):
    result = api_client.is_mailing_list_message(USER_ID, NAMESPACE_ID,
            TEST_MSG['msg_id'])
    expected = True

    assert (result == expected)

def test_mailing_list_info_for_message(api_client):
    result = api_client.mailing_list_info_for_message(USER_ID, NAMESPACE_ID,
            TEST_MSG['msg_id'])
    expected = json.dumps(TEST_MSG['mailing_list_headers'],
            default=json_util.default)

    assert (result == expected)

def test_headers_for_message(api_client):
    result = api_client.headers_for_message(USER_ID, NAMESPACE_ID,
            TEST_MSG['msg_id'])
    expected = json.dumps(TEST_MSG['all_headers'], default=json_util.default)

    assert(result == expected)

## TEST MESSAGE ##
TEST_MSG = {
        'msg_id': 2,
        'mailing_list_headers': { "List-Id": "<golang-nuts.googlegroups.com>",
            "List-Post": "<http://groups.google.com/group/golang-nuts/post>, <mailto:golang-nuts@googlegroups.com>",
            "List-Owner": None,
            "List-Subscribe": "<http://groups.google.com/group/golang-nuts/subscribe>, <mailto:golang-nuts+subscribe@googlegroups.com>",
            "List-Unsubscribe": "<http://groups.google.com/group/golang-nuts/subscribe>, <mailto:googlegroups-manage+332403668183+unsubscribe@googlegroups.com>",
            "List-Archive": "<http://groups.google.com/group/golang-nuts>",
            "List-Help": "<http://groups.google.com/support/>, <mailto:golang-nuts+help@googlegroups.com>"
            },
        'all_headers' : [["Delivered-To", "testinboxapp@gmail.com"],
            ["Received", "by 10.112.137.200 with SMTP id qk8csp326092lbb;        Wed, 22 Jan 2014 21:19:34 -0800 (PST)"],
            ["Return-Path", "<golang-nuts+bncBC4O7BEG6MLRBX6MQKLQKGQEF2AXJ7Q@googlegroups.com>"],
            ["Received-Spf", "pass (google.com: domain of golang-nuts+bncBC4O7BEG6MLRBX6MQKLQKGQEF2AXJ7Q@googlegroups.com designates 10.50.134.169 as permitted sender) client-ip=10.50.134.169"],
            ["Authentication-Results", "mr.google.com;       spf=pass (google.com: domain of golang-nuts+bncBC4O7BEG6MLRBX6MQKLQKGQEF2AXJ7Q@googlegroups.com designates 10.50.134.169 as permitted sender) smtp.mail=golang-nuts+bncBC4O7BEG6MLRBX6MQKLQKGQEF2AXJ7Q@googlegroups.com;       dkim=pass header.i=@googlegroups.com"],
            ["X-Received", "from mr.google.com ([10.50.134.169])        by 10.50.134.169 with SMTP id pl9mr1431876igb.17.1390454374598 (num_hops = 1);        Wed, 22 Jan 2014 21:19:34 -0800 (PST)"],
            ["Dkim-Signature", "v=1; a=rsa-sha256; c=relaxed/relaxed;        d=googlegroups.com; s=20120806;        h=mime-version:in-reply-to:references:from:date:message-id:subject:to         :cc:x-original-sender:x-original-authentication-results:precedence         :mailing-list:list-id:list-post:list-help:list-archive:sender         :list-subscribe:list-unsubscribe:content-type;        bh=7YuR8e+1m/OsteeChPEgx4j6hLx/Om+Ja9wJ8RdwXP8=;        b=Jhu2ZwKRW0BTrAAGmc3lan+ozy/xe8ZqWcrpGVDUiah2OOY2mtobDvcQfxcf0JdCeJ         b2ZoEv+DqJ5FQ/UYl3EQqGGKPUiXWOtNOzFzffh/FggMCXLZ25yWyageEnIDVRfmU9ra         XZq9GbbNz5cIErQzxO8hCmXe4arSgGQ9Ujxu1xvNSM8kH6cSeXhlNoRpA6dgPKTqG3wJ         P+134purR89lPq1LH6yKqqSd+rOzv9ANF3v9ertbR/YZT95N8C/W/ayy1NGcpTvOcbfZ         sPLWiEig6BQ0IblH9g8/NlEs92NSiLcptMAtjwnu1bNQeByR4mFVfbIsVgZ+Oq1xELDw         QQTw=="],
            ["X-Received", "by 10.50.134.169 with SMTP id pl9mr139297igb.17.1390454373977;        Wed, 22 Jan 2014 21:19:33 -0800 (PST)"], ["X-Beenthere", "golang-nuts@googlegroups.com"], ["Received", "by 10.50.73.201 with SMTP id n9ls187273igv.13.gmail; Wed, 22 Jan 2014 21:19:27 -0800 (PST)"], ["X-Received", "by 10.66.189.163 with SMTP id gj3mr2226946pac.32.1390454367313;        Wed, 22 Jan 2014 21:19:27 -0800 (PST)"], ["Received", "from mail-vc0-x22a.google.com (mail-vc0-x22a.google.com [2607:f8b0:400c:c03::22a])        by gmr-mx.google.com with ESMTPS id 48si4477719yhf.7.2014.01.22.21.19.27        for <golang-nuts@googlegroups.com>        (version=TLSv1 cipher=ECDHE-RSA-RC4-SHA bits=128/128);        Wed, 22 Jan 2014 21:19:27 -0800 (PST)"],
            ["Received-Spf", "pass (google.com: domain of ncc1701zzz@gmail.com designates 2607:f8b0:400c:c03::22a as permitted sender) client-ip=2607:f8b0:400c:c03::22a;"], ["Received", "by mail-vc0-f170.google.com with SMTP id hu8so797143vcb.29        for <golang-nuts@googlegroups.com>; Wed, 22 Jan 2014 21:19:27 -0800 (PST)"],
            ["X-Received", "by 10.58.90.1 with SMTP id bs1mr3327649veb.29.1390454367058; Wed, 22 Jan 2014 21:19:27 -0800 (PST)"],
            ["Mime-Version", "1.0"],
            ["Received", "by 10.58.117.226 with HTTP; Wed, 22 Jan 2014 21:19:07 -0800 (PST)"],
            ["In-Reply-To", "<CANp9fE9JJ6O19wj=r3CyqTXTJ9vYwUsTD0Fx9xyVGK5OmPKBBw@mail.gmail.com>"],
            ["References", "<9caff450-3bd2-435f-8ee9-0c38af4b545c@googlegroups.com> <91cb1fd5-061d-4c51-90b9-df11f6c99bcd@googlegroups.com> <CANp9fE-TEWYxOKZUnXwzzeE8DjC1gtG10YQCRg5ENCSoZ6fA2g@mail.gmail.com> <52E03649.8060107@gmail.com> <52E03742.3050405@gmail.com> <CANp9fE_w3QV=DGPxR4pTX-vcBi_UPSifc+aqB4zcamniWmOnfw@mail.gmail.com> <52E04679.3070207@gmail.com> <CANp9fE9JJ6O19wj=r3CyqTXTJ9vYwUsTD0Fx9xyVGK5OmPKBBw@mail.gmail.com>"],
            ["From", "Nacho <ncc1701zzz@gmail.com>"], ["Date", "Thu, 23 Jan 2014 06:19:07 +0100"],
            ["Message-Id", "<CA+Ac+URsAJkqXVau6C0BME=Yc40=TFHcnfyV4=aT7+GrD2oYXA@mail.gmail.com>"],
            ["Subject", "Re: [go-nuts] Re: Weird behaviour of Go compiler."],
            ["To", "Dave Cheney <dave@cheney.net>"],
            ["Cc", "\"N. Riesco - GMail account\" <nicolas.riesco@gmail.com>, golang-nuts <golang-nuts@googlegroups.com>"],
            ["X-Original-Sender", "ncc1701zzz@gmail.com"],
            ["X-Original-Authentication-Results", "gmr-mx.google.com;       spf=pass (google.com: domain of ncc1701zzz@gmail.com designates 2607:f8b0:400c:c03::22a as permitted sender) smtp.mail=ncc1701zzz@gmail.com;       dkim=pass header.i=@gmail.com;       dmarc=pass (p=NONE dis=NONE) header.from=gmail.com"],
            ["Precedence", "list"], ["Mailing-List", "list golang-nuts@googlegroups.com; contact golang-nuts+owners@googlegroups.com"],
            ["List-Id", "<golang-nuts.googlegroups.com>"], ["X-Google-Group-Id", "332403668183"],
            ["List-Post", "<http://groups.google.com/group/golang-nuts/post>, <mailto:golang-nuts@googlegroups.com>"],
            ["List-Help", "<http://groups.google.com/support/>, <mailto:golang-nuts+help@googlegroups.com>"],
            ["List-Archive", "<http://groups.google.com/group/golang-nuts>"], ["Sender", "golang-nuts@googlegroups.com"],
            ["List-Subscribe", "<http://groups.google.com/group/golang-nuts/subscribe>, <mailto:golang-nuts+subscribe@googlegroups.com>"],
            ["List-Unsubscribe", "<http://groups.google.com/group/golang-nuts/subscribe>, <mailto:googlegroups-manage+332403668183+unsubscribe@googlegroups.com>"],
            ["Content-Type", ["multipart/alternative", {"boundary": "089e011845749fffd504f09c6275"}]]
            ]
        }
