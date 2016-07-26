def report_message_creation_latency(self, message):
    latency_millis = (
        datetime.utcnow() - message.received_date) \
        .total_seconds() * 1000
    metrics = [
        '.'.join(['accounts', 'overall', 'message_latency']),
        '.'.join(['providers', self.provider_name, 'message_latency']),
    ]
    for metric in metrics:
        statsd_client.timing(metric, latency_millis)


def report_first_message(self):
    now = datetime.utcnow()

    with session_scope(self.namespace_id) as db_session:
        account = db_session.query(Account).get(self.account_id)
        account_created = account.created_at

    latency = (now - account_created).total_seconds() * 1000
    metrics = [
        '.'.join(['providers', self.provider_name, 'first_message']),
        '.'.join(['providers', 'overall', 'first_message'])
    ]

    for metric in metrics:
        statsd_client.timing(metric, latency)

def report_message_velocity(self, timedelta, num_uids):
    latency = (timedelta).total_seconds() * 1000
    latency_per_uid = float(latency) / num_uids
    metrics = [
        '.'.join(['providers', self.provider_name,
                  'message_velocity']),
        '.'.join(['providers', 'overall', 'message_velocity'])
    ]
    for metric in metrics:
        statsd_client.timing(metric, latency_per_uid)
