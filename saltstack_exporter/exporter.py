import argparse
import logging
import threading
import sys
import time
import re
from subprocess import Popen,PIPE
from tornado import web, ioloop
from prometheus_client import generate_latest
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.core import CounterMetricFamily
from prometheus_client.core import REGISTRY


parser = argparse.ArgumentParser()
parser.add_argument(
    '--listen-addr',
    help='address to bind to (default: 0.0.0.0)',
    default=''
)
parser.add_argument(
    '--listen-port',
    type=int,
    help='port to bind to (default: 9175)',
    default='9175'
)
parser.add_argument(
    '--highstate-interval',
    type=int,
    help='seconds between each highstate test run (default: 300)',
    default='300'
)
parser.add_argument(
    '--log-level',
    help='log level (default: WARN)',
    default=logging.WARN
)
args = parser.parse_args()
log = logging.getLogger(__name__)

class SaltHighstateCollector(object):
    def __init__(self, highstate_interval):
        self.statedata = None
        self.last_highstate = 0
        self.state_id_regex = re.compile(r'\s+ID:.*')
        self.state_error_regex = re.compile(r'\s+Result: False')
        self.state_none_regex = re.compile(r'\s+Result: None')

        self.states_total = lambda sample: GaugeMetricFamily(
            'saltstack_states_total',
            'Number of states which apply to the minion in highstate',
            value=sample
        )
        self.states_nonhigh = lambda sample: GaugeMetricFamily(
            'saltstack_nonhigh_states',
            'Number of states which would change on state.highstate',
            value=sample
        )
        self.states_error = lambda sample: GaugeMetricFamily(
            'saltstack_error_states',
            'Number of states which returns an error on highstate dry-run',
            value=sample
        )
        self.states_last_highstate = lambda sample: CounterMetricFamily(
            'saltstack_last_highstate',
            'Timestamp of the last highstate test run',
            value=sample
        )

        # Start worker thread that will collect metrics async
        thread = threading.Thread(target=self.collect_worker, args=(highstate_interval,))
        try:
            thread.setDaemon(True)
            thread.start()
        except (KeyboardInterrupt, SystemExit):
            thread.join(0)
            sys.exit()

    def describe(self):
        # Running highstate on startup can be slow, so we describe instead
        yield self.states_total(None)
        yield self.states_nonhigh(None)
        yield self.states_error(None)
        yield self.states_last_highstate(None)

    def collect(self):
        success = isinstance(self.statedata, list)

        if not success:
            log.error('Failed to collect Highstate. Return data: {0}'.format(self.statedata))
            return

        states = list(filter(
            self.state_id_regex.search,
            self.statedata
        ))
        yield self.states_total(len(states))

        nonhigh = list(filter(
            self.state_none_regex.search,
            self.statedata
        ))
        yield self.states_nonhigh(len(nonhigh))

        error = list(filter(
            self.state_error_regex.search,
            self.statedata
        ))
        yield self.states_error(len(error))

        yield self.states_last_highstate(self.last_highstate)

    def collect_worker(self, highstate_interval):
        while True:
            p = Popen('salt-call state.highstate test=t'.split(),
                             shell=False,
                             stdout=PIPE,
                             stderr=PIPE)
            self.statedata = p.communicate()[0].split('\n')
            self.last_highstate = int(time.time())
            time.sleep(highstate_interval)

class RootHandler(web.RequestHandler):
    def get(self):
        self.set_status(200)
        self.write(
            '<h1>Saltstack Collector</h1>'
            '<a href="/metrics">Metrics</a>'
        )


class HealthcheckHandler(web.RequestHandler):
    def get(self):
        self.write('OK')

    def head(self):
        self.set_status(200)


# This is a tornado-adapted handled from prometheus_client.MetricsHandler
class MetricsHandler(web.RequestHandler):
    def get(self):
        try:
            output = generate_latest(REGISTRY)
        except:
            self.set_status(500, 'error generating metric output')
            raise
        self.set_status(200)
        self.set_header('Content-Type', CONTENT_TYPE_LATEST)
        self.write(output)


def init_logging():
    loggers = [__name__, 'tornado.access', 'tornado.application', 'tornado.general']
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.propagate = False
        logger.setLevel(args.log_level)
        stdout_handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(stdout_handler)

def main():
    REGISTRY.register(SaltHighstateCollector(args.highstate_interval))

    init_logging()

    app = web.Application([
        (r'/', RootHandler),
        (r'/healthcheck', HealthcheckHandler),
        (r'/metrics', MetricsHandler)
    ])
    app.listen(args.listen_port, args.listen_addr)

    print('Serving metrics on {}:{}'.format(args.listen_addr, args.listen_port))
    ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
