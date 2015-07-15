import statsd

from inbox.config import config

statsd_client = statsd.StatsClient(
    config.get("STATSD_HOST", "localhost"),
    config.get("STATSD_PORT", 8125),
    prefix=config.get("STATSD_PREFIX", "mailsync")
)
