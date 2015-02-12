from ast import literal_eval

from inbox.heartbeat.config import REPORT_DATABASE, _get_redis_client


class ReportEntry(object):

    def __init__(self, alive=True, email_address=u'', provider_name=u''):
        self.alive = alive
        self.email_address = email_address
        self.provider_name = provider_name

    def __repr__(self):
        return str((self.alive, self.email_address, self.provider_name))

    @classmethod
    def from_string(cls, string_value):
        value = literal_eval(string_value)
        return cls(value[0], value[1], value[2])


def construct_heartbeat_report(status):
    assert status is not None
    report = {}
    for account_id, account in status.iteritems():
        # if missing, do nothing... but this isn't supposed to happen
        if account.missing:
            continue
        report[account_id] = ReportEntry(account.alive,
                                         account.email_address,
                                         account.provider_name)
    return report


def fetch_heartbeat_report(host, port):
    client = _get_redis_client(host, port, REPORT_DATABASE)
    batch_client = client.pipeline()
    names = []
    for name in client.scan_iter(count=100):
        if name == 'ElastiCacheMasterReplicationTimestamp':
            continue
        names.append(int(name))
        batch_client.get(name)
    values = map(ReportEntry.from_string, batch_client.execute())
    return dict(zip(names, values))


def store_heartbeat_report(host, port, report):
    if not report:
        return
    client = _get_redis_client(host, port, REPORT_DATABASE)
    batch_client = client.pipeline()
    # flush the db to avoid stale information
    batch_client.flushdb()
    for name, value in report.iteritems():
        batch_client.set(name, value)
    batch_client.execute()


def diff_heartbeat_reports(report, new_report):
    assert report is not None
    assert new_report is not None
    dead = []
    new_dead = []
    for name, new_value in new_report.iteritems():
        # if alive, do nothing
        if new_value.alive:
            continue
        # make the default True to eagerly signal new dead accounts
        value = report.get(name, ReportEntry())
        if value.alive:
            # new dead account, since previously was alive
            new_dead.append((name, value.email_address, value.provider_name))
        else:
            # already dead account
            dead.append((name, value.email_address, value.provider_name))
    return (sorted(dead, key=lambda t: t[0]),
            sorted(new_dead, key=lambda t: t[0]))
