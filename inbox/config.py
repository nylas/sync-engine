import errno
import os
import yaml

# TODO[mike]: This should be removed once we've updated python to 2.7.9
# This tells urllib3 to use pyopenssl, which has the latest tls protocols and is
# more secure than the default python ssl module in python 2.7.4
import requests
import urllib3.contrib.pyopenssl
urllib3.contrib.pyopenssl.inject_into_urllib3()
urllib3.disable_warnings()
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# TODO[mike]: This shold be removed once we've updated our base OS. openssl 1.0.1 doesn't support cross-signed certs
# https://github.com/certifi/python-certifi/issues/26#issuecomment-138322515
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.old_where()


__all__ = ['config']


if 'NYLAS_ENV' in os.environ:
    assert os.environ['NYLAS_ENV'] in ('dev', 'test', 'staging', 'prod'), \
        "NYLAS_ENV must be either 'dev', 'test', staging, or 'prod'"
    env = os.environ['NYLAS_ENV']
else:
    env = 'prod'


def is_live_env():
    return env == 'prod' or env == 'staging'


class ConfigError(Exception):

    def __init__(self, error=None, help=None):
        self.error = error or ''
        self.help = help or \
            'Run `sudo cp etc/config-dev.json /etc/inboxapp/config.json` and retry.'

    def __str__(self):
        return '{0} {1}'.format(self.error, self.help)


class Configuration(dict):

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

    def get_required(self, key):
        if key not in self:
            raise ConfigError('Missing config value for {0}.'.format(key))

        return self[key]


def _update_config_from_env(config, env):
    """
    Update a config dictionary from configuration files specified in the
    environment.

    The environment variable `SYNC_ENGINE_CFG_PATH` contains a list of .json or .yml
    paths separated by colons.  The files are read in reverse order, so that
    the settings specified in the leftmost configuration files take precedence.
    (This is to emulate the behavior of the unix PATH variable, but the current
    implementation always reads all config files.)

    The following paths will always be appended:

    If `NYLAS_ENV` is 'prod':
      /etc/inboxapp/secrets.yml:/etc/inboxapp/config.json

    If `NYLAS_ENV` is 'test':
      {srcdir}/etc/secrets-test.yml:{srcdir}/etc/config-test.yml

    If `NYLAS_ENV` is 'dev':
      {srcdir}/etc/secrets-dev.yml:{srcdir}/etc/config-dev.yml

    Missing files in the path will be ignored.

    """
    srcdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')

    if env in ['prod', 'staging']:
        base_cfg_path = [
            '/etc/inboxapp/secrets.yml',
            '/etc/inboxapp/config.json',
        ]
    else:
        v = {'env': env, 'srcdir': srcdir}
        base_cfg_path = [
            '{srcdir}/etc/secrets-{env}.yml'.format(**v),
            '{srcdir}/etc/config-{env}.json'.format(**v),
        ]

    if 'SYNC_ENGINE_CFG_PATH' in os.environ:
        cfg_path = os.environ.get('SYNC_ENGINE_CFG_PATH', '').split(os.path.pathsep)
        cfg_path = list(p.strip() for p in cfg_path if p.strip())
    else:
        cfg_path = []

    path = cfg_path + base_cfg_path

    for filename in reversed(path):
        try:
            f = open(filename)
        except (IOError, OSError) as e:
            if e.errno != errno.ENOENT:
                raise
        else:
            with f:
                # this also parses json, which is a subset of yaml
                config.update(yaml.safe_load(f))


def _get_local_feature_flags(config):
    if os.environ.get('FEATURE_FLAGS') is not None:
        flags = os.environ.get('FEATURE_FLAGS').split()
    else:
        flags = config.get('FEATURE_FLAGS', '').split()
    config['FEATURE_FLAGS'] = flags


def _get_process_name(config):
    if os.environ.get('PROCESS_NAME') is not None:
        config['PROCESS_NAME'] = os.environ.get("PROCESS_NAME")

config = Configuration()
_update_config_from_env(config, env)
_get_local_feature_flags(config)
_get_process_name(config)
