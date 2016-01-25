#!/usr/bin/env python
import random
import subprocess
import time

from sqlalchemy import func

from inbox.util.blockstore import get_from_blockstore
from inbox.models.message import Message
from inbox.models.session import session_scope

with session_scope(0) as db_session:
    max_msg_id = db_session.query(func.max(Message.id)).scalar()

    msg_ids = [random.randint(1, max_msg_id) for i in xrange(500)]

    object_keys = [t for t, in db_session.query(Message.data_sha256).filter(
        Message.id.in_(msg_ids)).all()]

    gzip_results = []
    gzip_best_results = []
    bzip_results = []

    for key in object_keys:
        data = get_from_blockstore(key)

        start_time = time.time()
        p = subprocess.Popen('gzip -c'.split(),
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        gzip_compressed_data, stderr = p.communicate(data)
        gzip_elapsed = time.time() - start_time
        gzip_ratio = len(data) / float(len(gzip_compressed_data))
        gzip_results.append((gzip_ratio, gzip_elapsed))

        start_time = time.time()
        p = subprocess.Popen('gzip -9 -c'.split(),
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        gzip_best_compressed_data, stderr = p.communicate(data)
        gzip_best_elapsed = time.time() - start_time
        gzip_best_ratio = len(data) / float(len(gzip_best_compressed_data))
        gzip_best_results.append((gzip_best_ratio, gzip_best_elapsed))

        p = subprocess.Popen('bzip2 -c'.split(),
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        bzip_compressed_data, stderr = p.communicate(data)
        bzip_elapsed = time.time() - start_time
        bzip_ratio = len(data) / float(len(bzip_compressed_data))
        bzip_results.append((bzip_ratio, bzip_elapsed))

        print key, len(data), "{:.2f}({:e}s) {:.2f}({:e}s) {:.2f}({:e}s)"\
            .format(gzip_ratio, gzip_elapsed,
                    gzip_best_ratio, gzip_best_elapsed,
                    bzip_ratio, bzip_elapsed)

    print

    gzip_ratio_average = sum([rate for rate, elapsed in gzip_results]) / len(gzip_results)
    gzip_elapsed_average = sum([elapsed for rate, elapsed in gzip_results]) / len(gzip_results)
    print "Gzip summary: {:.2f} ({:e})s".format(gzip_ratio_average, gzip_elapsed_average)

    gzip_best_ratio_average = sum([rate for rate, elapsed in gzip_best_results]) / len(gzip_best_results)
    gzip_best_elapsed_average = sum([elapsed for rate, elapsed in gzip_best_results]) / len(gzip_best_results)
    print "Gzip best summary: {:.2f} ({:e})s".format(gzip_best_ratio_average, gzip_best_elapsed_average)

    bzip_ratio_average = sum([rate for rate, elapsed in bzip_results]) / len(bzip_results)
    bzip_elapsed_average = sum([elapsed for rate, elapsed in bzip_results]) / len(bzip_results)
    print "bzip summary: {:.2f} ({:e})s".format(bzip_ratio_average, bzip_elapsed_average)
