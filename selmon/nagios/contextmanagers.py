from selmon.nagios.nagiosmessage import NagiosMessage
from selmon.nagios.plugin import SelmonTestException
from contextlib import contextmanager
import time


@contextmanager
def benchmark(nagios_message, label, warning=3, critical=5):
    start_time = time.time()
    yield
    elapsed = time.time() - start_time
    nagios_message.add_msg('%s executed in %s seconds' % (label, format(elapsed,".2f")))
    nagios_message.add_perfdata(
        label, NagiosMessage.UOM_SEC, elapsed,
        warning, critical
    )

    if elapsed > critical:
        nagios_message.add_msg("'%s' exceeded critical threshold of %s" %
                               (label, critical))
        nagios_message.raise_status(NagiosMessage.NAGIOS_STATUS_CRITICAL)
    elif elapsed > warning:
        nagios_message.add_msg("'%s' exceeded warning threshold of %s" %
                               (label, warning))
        nagios_message.raise_status(NagiosMessage.NAGIOS_STATUS_WARNING)


@contextmanager
def test(nagios_message, label, status=NagiosMessage.NAGIOS_STATUS_CRITICAL):
    try:
        yield
    except SelmonTestException:
        nagios_message.add_msg("Test failed: '%s'" % label)
        nagios_message.raise_status(status)
