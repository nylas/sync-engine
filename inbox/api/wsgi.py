from inbox.config import config

import nylas.api.wsgi

from nylas.api.wsgi import (NylasWSGIHandler, NylasWSGIWorker,
                            NylasGunicornLogger)

nylas.api.wsgi.MAX_BLOCKING_TIME = config.get('MAX_BLOCKING_TIME',
                                              nylas.api.wsgi.MAX_BLOCKING_TIME)
nylas.api.wsgi.LOGLEVEL = config.get('LOGLEVEL',
                                     nylas.api.wsgi.LOGLEVEL)

# legacy names for backcompat
InboxWSGIWorker = NylasWSGIWorker
GunicornLogger = NylasGunicornLogger


__all__ = ['NylasWSGIHandler', 'NylasWSGIWorker', 'NylasGunicornLogger',
           'InboxWSGIWorker', 'GunicornLogger']
