from flanker import mime
import json

# Email from the sync dump exported to the 'test' db 
message = '''Delivered-To: inboxapptest@gmail.com
Received: by 10.112.78.5 with SMTP id x5csp319417lbw;
        Wed, 5 Feb 2014 18:07:03 -0800 (PST)
X-Received: by 10.224.34.71 with SMTP id k7mr8238891qad.15.1391652423038;
        Wed, 05 Feb 2014 18:07:03 -0800 (PST)
Return-Path: <christine@spang.cc>
Received: from relay5-d.mail.gandi.net (relay5-d.mail.gandi.net. [2001:4b98:c:538::197])
        by mx.google.com with ESMTPS id z6si7251472qan.191.2014.02.05.18.07.01
        for <inboxapptest@gmail.com>
        (version=TLSv1 cipher=RC4-SHA bits=128/128);
        Wed, 05 Feb 2014 18:07:02 -0800 (PST)
Received-SPF: neutral (google.com: 2001:4b98:c:538::197 is neither permitted nor denied by best guess record for domain of christine@spang.cc) client-ip=2001:4b98:c:538::197;
Authentication-Results: mx.google.com;
       spf=neutral (google.com: 2001:4b98:c:538::197 is neither permitted nor denied by best guess record for domain of christine@spang.cc) smtp.mail=christine@spang.cc
Received: from mfilter2-d.gandi.net (mfilter2-d.gandi.net [217.70.178.140])
	by relay5-d.mail.gandi.net (Postfix) with ESMTP id A4C8E41C05A
	for <inboxapptest@gmail.com>; Thu,  6 Feb 2014 03:07:00 +0100 (CET)
X-Virus-Scanned: Debian amavisd-new at mfilter2-d.gandi.net
Received: from relay5-d.mail.gandi.net ([217.70.183.197])
	by mfilter2-d.gandi.net (mfilter2-d.gandi.net [10.0.15.180]) (amavisd-new, port 10024)
	with ESMTP id mY4bRLSiQ6xS for <inboxapptest@gmail.com>;
	Thu,  6 Feb 2014 03:06:58 +0100 (CET)
X-Originating-IP: 78.47.252.235
Received: from localhost (spang.cc [78.47.252.235])
	(Authenticated sender: christine@spang.cc)
	by relay5-d.mail.gandi.net (Postfix) with ESMTPSA id 09E8941C053
	for <inboxapptest@gmail.com>; Thu,  6 Feb 2014 03:06:57 +0100 (CET)
Resent-From: Christine Spang <christine@spang.cc>
Resent-Date: Thu, 6 Feb 2014 02:06:57 +0000
Resent-Message-ID: <20140206020657.GA14542@spang>
Resent-To: inboxapptest@gmail.com
Received: from spool.mail.gandi.net (mspool7-d.mgt.gandi.net [10.0.21.138])
	by nmboxes2-d.mgt.gandi.net (Postfix) with ESMTP id EC97D24562C
	for <christine@spang.cc>; Sat, 11 May 2013 11:12:31 +0200 (CEST)
Received: from mfilter13-d.gandi.net (mfilter13-d.gandi.net [217.70.178.141])
	by spool.mail.gandi.net (Postfix) with ESMTP id E983419F38B
	for <christine@spang.cc>; Sat, 11 May 2013 11:12:31 +0200 (CEST)
X-Virus-Scanned: Debian amavisd-new at mfilter13-d.gandi.net
Received: from spool.mail.gandi.net ([10.0.21.138])
	by mfilter13-d.gandi.net (mfilter13-d.gandi.net [10.0.15.180]) (amavisd-new, port 10024)
	with ESMTP id 1zi9yjBtRI9f for <christine@spang.cc>;
	Sat, 11 May 2013 11:12:29 +0200 (CEST)
Received: from dmz-mailsec-scanner-7.mit.edu (DMZ-MAILSEC-SCANNER-7.MIT.EDU [18.7.68.36])
	by spool.mail.gandi.net (Postfix) with ESMTP id 1DF4019F385
	for <christine@spang.cc>; Sat, 11 May 2013 11:12:28 +0200 (CEST)
Received: from mailhub-dmz-2.mit.edu ( [18.7.62.37])
	by dmz-mailsec-scanner-7.mit.edu (Symantec Messaging Gateway) with SMTP id C4.E5.10436.B7B0E815; Sat, 11 May 2013 05:12:28 -0400 (EDT)
Received: from dmz-mailsec-scanner-5.mit.edu (DMZ-MAILSEC-SCANNER-5.MIT.EDU [18.7.68.34])
	by mailhub-dmz-2.mit.edu (8.13.8/8.9.2) with ESMTP id r4B9C79O005530
	for <spang@mit.edu>; Sat, 11 May 2013 05:12:26 -0400
X-AuditID: 12074424-b7f8c6d0000028c4-a0-518e0b7b0184
Authentication-Results: symauth.service.identifier
Received: from bendel.debian.org (bendel.debian.org [82.195.75.100])
	by dmz-mailsec-scanner-5.mit.edu (Symantec Messaging Gateway) with SMTP id F9.C1.02397.A7B0E815; Sat, 11 May 2013 05:12:26 -0400 (EDT)
Received: from localhost (localhost [127.0.0.1])
	by bendel.debian.org (Postfix) with QMQP
	id 0592C375; Sat, 11 May 2013 09:12:17 +0000 (UTC)
Old-Return-Path: <debbugs@buxtehude.debian.org>
X-Original-To: lists-debian-devel@bendel.debian.org
Received: from localhost (localhost [127.0.0.1])
	by bendel.debian.org (Postfix) with ESMTP id CEE53310
	for <lists-debian-devel@bendel.debian.org>; Sat, 11 May 2013 09:12:16 +0000 (UTC)
X-Virus-Scanned: at lists.debian.org with policy bank en-ht
Received: from bendel.debian.org ([127.0.0.1])
	by localhost (lists.debian.org [127.0.0.1]) (amavisd-new, port 2525)
	with ESMTP id wXP6FTYIyEPW for <lists-debian-devel@bendel.debian.org>;
	Sat, 11 May 2013 09:12:10 +0000 (UTC)
Received: from buxtehude.debian.org (buxtehude.debian.org [140.211.166.26])
	(using TLSv1 with cipher DHE-RSA-AES128-SHA (128/128 bits))
	(Client did not present a certificate)
	by bendel.debian.org (Postfix) with ESMTPS id DE6611BD;
	Sat, 11 May 2013 09:12:09 +0000 (UTC)
Received: from debbugs by buxtehude.debian.org with local (Exim 4.80)
	(envelope-from <debbugs@buxtehude.debian.org>)
	id 1Ub5qY-0002MO-Cc; Sat, 11 May 2013 09:12:06 +0000
X-Loop: owner@bugs.debian.org
Subject: Bug#707777: ITP: node-cookie -- Basic cookie parser and serializer module for Node.js
Reply-To: =?UTF-8?Q?J=C3=A9r=C3=A9my?= Lal <kapouer@melix.org>,
        707777@bugs.debian.org
Resent-From: =?UTF-8?Q?J=C3=A9r=C3=A9my?= Lal <kapouer@melix.org>
Resent-To: debian-bugs-dist@lists.debian.org
Resent-CC: debian-devel@lists.debian.org, wnpp@debian.org,
        "=?UTF-8?Q?J=C3=A9r=C3=A9my?= Lal" <kapouer@melix.org>
X-Loop: owner@bugs.debian.org
Resent-Date: Sat, 11 May 2013 09:12:02 +0000
Resent-Message-ID: <handler.707777.B.13682633676382@bugs.debian.org>
X-Debian-PR-Message: report 707777
X-Debian-PR-Package: wnpp
X-Debian-PR-Keywords: 
Received: via spool by submit@bugs.debian.org id=B.13682633676382
          (code B); Sat, 11 May 2013 09:12:02 +0000
Received: (at submit) by bugs.debian.org; 11 May 2013 09:09:27 +0000
X-Spam-Bayes: score:0.0000 Tokens: new, 17; hammy, 149; neutral, 33; spammy,
	0. spammytokens: hammytokens:0.000-+--H*M:reportbug, 0.000-+--H*MI:reportbug,
	0.000-+--H*x:reportbug, 0.000-+--H*UA:reportbug,
	0.000-+--HX-Debbugs-Cc:sk:debian-
Received: from mx1.polytechnique.org ([129.104.30.34])
	by buxtehude.debian.org with esmtps (TLS1.0:DHE_RSA_AES_256_CBC_SHA1:256)
	(Exim 4.80)
	(envelope-from <SRS0=iAH5=O4=melix.org=kapouer@bounces.m4x.org>)
	id 1Ub5nx-0001eZ-Vz
	for submit@bugs.debian.org; Sat, 11 May 2013 09:09:27 +0000
Received: from imac.chaumes (lns-bzn-47f-81-56-208-91.adsl.proxad.net [81.56.208.91])
	(using TLSv1 with cipher DHE-RSA-AES128-SHA (128/128 bits))
	(No client certificate requested)
	by ssl.polytechnique.org (Postfix) with ESMTPSA id 18FB2140C5BA2;
	Sat, 11 May 2013 11:09:20 +0200 (CEST)
Received: from dev by imac.chaumes with local (Exim 4.80)
	(envelope-from <kapouer@melix.org>)
	id 1Ub5nr-0003km-6N; Sat, 11 May 2013 11:09:19 +0200
MIME-Version: 1.0
Content-Type: text/plain; charset="UTF-8"
From: =?UTF-8?Q?J=C3=A9r=C3=A9my?= Lal <kapouer@melix.org>
To: Debian Bug Tracking System <submit@bugs.debian.org>
Message-ID: <20130511090919.14332.37267.reportbug@imac.chaumes>
X-Mailer: reportbug 6.4.4
Date: Sat, 11 May 2013 11:09:19 +0200
X-AV-Checked: ClamAV using ClamSMTP at svoboda.polytechnique.org (Sat May 11 11:09:20 2013 +0200 (CEST))
X-Org-Mail: jeremy.lal.1997@polytechnique.org
X-Rc-Virus: 2007-09-13_01
X-Mailing-List: <debian-devel@lists.debian.org> archive/latest/292739
X-Loop: debian-devel@lists.debian.org
List-Id: <debian-devel.lists.debian.org>
List-URL: <http://lists.debian.org/debian-devel/>
List-Post: <mailto:debian-devel@lists.debian.org>
List-Help: <mailto:debian-devel-request@lists.debian.org?subject=help>
List-Subscribe: <mailto:debian-devel-request@lists.debian.org?subject=subscribe>
List-Unsubscribe: <mailto:debian-devel-request@lists.debian.org?subject=unsubscribe>
Precedence: list
Resent-Sender: debian-devel-request@lists.debian.org
X-Brightmail-Tracker: H4sIAAAAAAAAA1WSbUhTYRTHe+7u5m167TqXHgfDuNkrrTcLC0sK+7CyKIP6EJFd3c2ttmm7
	zlQkBF8wqyG9WE1Kv0RmLe1FprMgFwVJy6zohUZGrVWrlFLJsKx796jRt/895/f/n/NcDiVT
	ORUaymQt4G1WzswqlKQqIm2WrjTSkbl4qJNcMeD8FbEG6Ue/XSW2oB3KVQbebCrkbYvSdiuN
	7933iPwqRVHHjStkGeona9BUCphlUF3nj8A6Dh69blHUICWlYm4h6PE3EFJDxTxH0OYzTxjG
	nnrCBsQshc6HITk2+BBU/PaR2FCLYOQrK+lpzCJo995B2JwMTQ2DYU2K5ra+AInNNxE8PR8c
	XyMVrvmbRIgS9TRweWfishpaj7nHt46G3o8jhOQF5hmC0Z6X44ODCE4fM+PQEwTUPffIccOF
	wHNci0O18OBliVSOZXbBue5mGUay4FNvn0JCVMxa+Ni+FJcXQMPPfoR1CQzWvUH/pVBh5ND3
	LEysg+b6IIG3ZKEleHX8UQnw+Nvlyf/sLruoqEWrneInzcTA/TMBUtIyJhHK2+plWM+DSvdo
	RCOSNSOtwVKis3Ams8Dn6IQczmrlbbqUhRZTwULeYL+GwoewLqkdlXtZL2IoxEbRM5ijmSo5
	VygUW7wogSLY6XS63JGpis7OMxQbOcGYZbObecGLgJKxajr4RsRpA1dcwtvyJlpzKYpxDwc6
	kYa05ll5FmiPUoyIsfG5fNEek1m8wwmUoKZKUVFi1F2JoYV8ziKYcnG/G+moqt7AZ6QKB2ni
	6UYJYiTIaLdO5kycdAjFi4+IpY9KVJR48JNJIXEIIQ7Zu/OwNKSA+9fSlCGH+tRY1/4TG/Jj
	vyQe7jhz/O3ssWTW7s5wpZ/uY4taV85RvtdHei9VeC60OBb/GHBRmyu2aj9sOTv84vqTd59f
	b9/mfBU6kpG0qT7JoCcHo5enV9+9fSpt+lBG5YE/bS6/ofVk8b7Upriu7BT9xsj17Ub7lIy4
	juCTg6VqX3KMWx3HkoKRWzJfZhO4v1Bc/fetAwAA
X-Brightmail-Tracker: H4sIAAAAAAAAA1WSbUhTURjHPbt3223uttu18mmlwa0PFi3Lit4sMv0gBJUJUhbZtZ3crW3a
	7pTph1imUloi2otm9C6oVFa0trQCJ/ai9iahSJYVtsJI0AiyKLp311l9Ofx5nt/z/z/ncCiC
	fa8xUtjlxA47b+U0OnJL2wazqSC8PGXR2KO4Fd1dHs06lFzY1U5sRum6eDO2CnnYEbt2l87y
	wftAlVOicd25dY10o2GyFE2igFkKv182a2WNmDhoeTqkVurT4fmbJk0p0lEs8wRB0a8nwQGW
	qUDw/QsnawMTCz5/G1IGlkD9ua9BTUpGnoFBUhm+i+BlXUCrQKvhZn+9BFGSNsBV/xylPBWu
	V3rHF6Kh8/jDYDAwPQh+PusbDw4gqK60KqbHVXCyt1mtNK4iaK6KUkyjoKuvQC5HMDvhbEcj
	oSBpcKL2nVZGWCYBPvnilPICODc2jBS9H3rr7xH/uVBB5MhohkIkQWNtQKVsyUFT4Mb4pWZA
	98gVbejZvO4GjcLnwa3ySiI0+722YfxWXxGMXm5XV6CVp6UezUyBxzWDpKwJZjYc8tQSip4H
	xd6f2vOIaERRZluBycYLVhHvNom7ebsdO0zLFtoE50Jszr2JpI/AapM4Hxpr5fyIoRCnpx9v
	PZbCqvk8Md/mRzMoFTeNTlSXp7CTM7PN+RZetGQ4cq1Y9COgCG4qHXgr4bSZzy/AjuxQayZF
	cpF0j7lvE8tk8U68D+Mc7Ah1VZTWj2IoivF+G2xBRtKebccc0Ak6KWWKA2dh1x7B6vyXnyQf
	OjlSL0VulEFazOFtopClQB3IRJW8GPyM2KCbMZJOlyFGhiy59gmz0NfvRlHGCBqFhYWxemkz
	6UH+7w+hSOkxIug02UUv2J0TSUPSEippib07yuQlnPzfltGNttcMgYco0RoebcRlB+P0de99
	mQFVS/he36KiXwkHere9uthUnFrV/9G0/IIn09Wd3XzJEF49J2/Np4770dFup+3onsIY84DR
	d8qdrDZcSQ37prm9XtA/jIX+WR/m8sxKIXH49eGykdan89rOxGd0DuQILueJzuSqVT0Z0y/W
	/+BI0cIvnk84RP4PBXntPvUDAAA=
Content-Transfer-Encoding: quoted-printable

Package: wnpp
Severity: wishlist
Owner: "J=C3=A9r=C3=A9my Lal" <kapouer@melix.org>

* Package name    : node-cookie
  Version         : 0.1.0
  Upstream Author : Roman Shtylman <shtylman@gmail.com>
* URL             : https://github.com/shtylman/node-cookie
* License         : Expat
  Programming Lang: JavaScript
  Description     : Basic cookie parser and serializer module for Node.js

node-cookie just provides a way to read and write RFC6265 HTTP cookie
headers.
.
Node.js is an event-based server-side javascript engine.


--=20
To UNSUBSCRIBE, email to debian-devel-REQUEST@lists.debian.org
with a subject of "unsubscribe". Trouble? Contact listmaster@lists.debian=
.org
Archive: http://lists.debian.org/20130511090919.14332.37267.reportbug@ima=
c.chaumes

'''

# Repr for testing
parsed = mime.from_string(message)
headers = json.dumps(parsed.headers.items())

TEST_MSG = {
	'msg_id': 1,
	'thread_id': 1,
	'mailing_list_headers': { "List-Id": "<debian-devel.lists.debian.org>", 
		"List-Post": "<mailto:debian-devel@lists.debian.org>", 
        "List-Owner": None, 
        "List-Subscribe": "<mailto:debian-devel-request@lists.debian.org?subject=subscribe>", 
        "List-Unsubscribe": "<mailto:debian-devel-request@lists.debian.org?subject=unsubscribe>", 
        "List-Archive": None, 
        "List-Help": "<mailto:debian-devel-request@lists.debian.org?subject=help>" 
        },
    'all_headers': headers
    }
