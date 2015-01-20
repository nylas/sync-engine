from inbox.heartbeat.config import REPORT_DATABASE, _get_redis_client


def make_heartbeat_report(status):
    assert status is not None
    report = {}
    for account_id, account_info in status.iteritems():
        report[account_id] = account_info[0]
    return report


def get_heartbeat_report(host, port):
    client = _get_redis_client(host, port, REPORT_DATABASE)
    batch_client = client.pipeline()
    names = []
    for name in client.scan_iter(count=100):
        if name == 'ElastiCacheMasterReplicationTimestamp':
            continue
        names.append(int(name))
        batch_client.get(name)
    values = map(lambda v: True if v == 'True' else False,
                 batch_client.execute())
    return dict(zip(names, values))


def set_heartbeat_report(host, port, report):
    if not report:
        return
    client = _get_redis_client(host, port, REPORT_DATABASE)
    batch_client = client.pipeline()
    # flush the db to avoid stale information
    batch_client.flushdb()
    for name, value in report.iteritems():
        batch_client.set(name, value)
    batch_client.execute()


def analyze_heartbeat_report(report, new_report):
    assert report is not None
    assert new_report is not None
    dead = []
    new_dead = []
    for name, new_value in new_report.iteritems():
        # if alive, do nothing
        if new_value:
            continue
        # make the default True to eagerly signal new dead accounts
        value = report.get(name, True)
        if value:
            # new dead account, since previously was alive
            new_dead.append(name)
        else:
            # already dead account
            dead.append(name)
    return (sorted(dead), sorted(new_dead))
