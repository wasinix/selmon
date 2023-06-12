import argparse
from selmon.nagios.nagiosmessage import NagiosMessage
from selmon.nagios.selmonremotedriver import SelmonRemoteDriver
from selenium.webdriver.remote.remote_connection import RemoteConnection
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.proxy import Proxy, ProxyType
import sys
import signal
import six
from datetime import datetime
import os


class Plugin(object):

    """
    Base object for creating a Nagios plugin that use Selenium Webdriver for
    web application monitoring. Basic usage involves creating a class that
    inherits from `Plugin` and implements the run() method. After creating
    the class, instantiate it and call its start() method (do NOT call the
    run() method directly, run() gets called by start()).

    The following example illustrates how to build a plugin that monitors
    duckduckgo.com, searches for 'selenium' and verifies that the text
    'selenium' is present on the result page

    from selenium.webdriver.common.keys import Keys
    from selmon.nagios.plugin import Plugin
    from selmon.nagios.contextmanagers import benchmark, test


    class DuckduckGoMonitor(Plugin):

        def run(self):
            driver = self.get_driver()

            with benchmark(self.nagios_message, 'open_homepage', warning=2):
                driver.get('https://duckduckgo.com/')

            search_elem = driver.find_element_by_name('q')
            search_elem.send_keys('selenium')

            with benchmark(self.nagios_message, 'submit_form'):
                search_elem.send_keys(Keys.RETURN)

            body_elem = driver.find_element_by_css_selector('body')

            with test(self.nagios_message, 'is my expected text there'):
                self.verify(driver.is_text_present_in_elem(
                                                    body_elem, 'selenium'))


    ddg_monitor = DuckduckGoMonitor()
    ddg_monitor.start()
    """

    capabilities_mapping = {
        'chrome': DesiredCapabilities.CHROME,
        'firefox': DesiredCapabilities.FIREFOX,
        'htmlunit': DesiredCapabilities.HTMLUNIT,
        'htmlunit_withjs': DesiredCapabilities.HTMLUNITWITHJS,
        'ie': DesiredCapabilities.INTERNETEXPLORER,
        'ipad': DesiredCapabilities.IPAD,
        'iphone': DesiredCapabilities.IPHONE,
        'safari': DesiredCapabilities.SAFARI
    }

    def __init__(self):
        """
        Plugin constructor. Since this base object gets inherited, there is no
        need to take care of command line arguments, as the base object already
        does it for you. Run the following to see what parameters your script
        automatically expects while inheriting from Plugin:
        ./yourscript.py -h
        """
        self.nagios_message = NagiosMessage()

        self.arg_parser = argparse.ArgumentParser(add_help=True)

        self.setup_default_args()

        # can be overridden in subclass
        self.add_extra_args()

        self.args = self.arg_parser.parse_args()

        if self.args.browser not in self.capabilities_mapping.keys():
            self.nagios_message.add_msg(
                'browser is invalid: %s' % self.args.browser)
            self.nagios_message.raise_status(
                NagiosMessage.NAGIOS_STATUS_UNKNOWN)
            sys.exit(self.nagios_message.status_code)

        self.global_timeout = self.args.timeout

        self.driver = None

    def setup_default_args(self):
        self.arg_parser.add_argument('-H', '--host',
                                     help='selenium webdriver remote host',
                                     required=True)
        self.arg_parser.add_argument(
            '-t',
            '--timeout',
            help='timeout in seconds to use for whole execution',
            required=True,
            type=int)
        self.arg_parser.add_argument(
            '-b',
            '--browser',
            help='browser to use, possible values: %s' %
            ','.join(
                self.capabilities_mapping.keys()),
            required=True)
        self.arg_parser.add_argument('-c', '--cert',
                                     help='certificate bundle pem format, to verify TLS enc of host',
                                     required=False)
        self.arg_parser.add_argument('--screenshot_path',
                                     help='if set, a final screenshot will be created at the end of the test in this path',
                                     required=False)
        self.arg_parser.add_argument('-p', '--proxy',
                                     help='proxy server to use',
                                     required=False)
        self.arg_parser.add_argument('-n', '--no_proxy', action='append',
                             help='urls, wildcards for which no proxy server should be used. \
                                   Needs to be combined with "-p". \
                                   Use multiple times for multiple exceptions.',
                             required=False)
        self.arg_parser.add_argument('--test_name',
                             help='Will be added as se:name to capabilities and then shown in Grid UI instead of session id. \
                                   Helps to identify different tests.',
                             required=False)

    def init_connection(self):
        try:
            self.conn = RemoteConnection(self.args.host)
            if self.args.cert:
                self.conn.set_certificate_bundle_path(self.args.cert)
        except Exception:
            exc_class, exc, tb = sys.exc_info()
            new_exc = ConnectionException(
                "Error connecting to Selenium server")
            six.reraise(new_exc.__class__, new_exc, tb)

    def init_driver(self):
        try:
            if self.args.proxy:
                prox = Proxy()
                prox.proxy_type = ProxyType.MANUAL
                prox.httpProxy = self.args.proxy
                prox.sslProxy = self.args.proxy
                if self.args.no_proxy:
                    prox.noProxy = self.args.no_proxy
                prox.add_to_capabilities(self.capabilities_mapping[self.args.browser])
            if self.args.test_name:
                self.capabilities_mapping[self.args.browser]["se:name"]=self.args.test_name
            self.driver = SelmonRemoteDriver(
                self.conn,
                self.capabilities_mapping[self.args.browser])
        except Exception:
            exc_class, exc, tb = sys.exc_info()
            six.reraise(DriverInitException, None, tb)

    def get_driver(self):
        """
        Returns the Selenium Remote webdriver instance
        """
        return self.driver

    def verify(self, boolean):
        if not boolean:
            raise SelmonTestException('verify failed')

    def run(self):
        """
        Override this method in your own plugin, then call start() on the newly
        created object (not run() itself!)
        """
        pass

    def add_extra_args(self):
        """
        To add extra arguments to your plugin, override this method and add
        arguments to self.arg_parser (an argparse ArgumentParser object). The
        argument values will be available in self.args
        """
        pass

    def start(self):
        """
        Call the start() method for actual execution of the plugin. It calls
        the run() method, creates a Nagios message and outputs it. Appropriate
        exit codes are determined during the test run and the plugin exits
        accordingly.
        """
        def timeout_handler(signum, frame):
            raise GlobalTimeoutException()

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.global_timeout)

        try:
            self.init_connection()
            self.init_driver()

            self.run()

        except WebDriverException as e:
            self.nagios_message.add_msg(
                'WebDriverException occurred: %s' % e.msg)
            self.nagios_message.raise_status(
                NagiosMessage.NAGIOS_STATUS_CRITICAL)
        except GlobalTimeoutException as e:
            self.nagios_message.add_msg(
                'Global timeout of %s seconds reached' % self.global_timeout)
            self.nagios_message.raise_status(
                NagiosMessage.NAGIOS_STATUS_CRITICAL)
        except ConnectionException:
            self.nagios_message.add_msg(
                'Could not connect to Selenium server at ' % self.args.host)
            self.nagios_message.raise_status(
                NagiosMessage.NAGIOS_STATUS_UNKNOWN)
        except DriverInitException as e:
            self.nagios_message.add_msg('Could not initialize Selenium driver')
            self.nagios_message.raise_status(
                NagiosMessage.NAGIOS_STATUS_UNKNOWN)
        except Exception as e:
            if not e.args:
                e.args = ('No message in exception',)

            self.nagios_message.add_msg(
                'FAILED: Exception of type: %s, message: %s' %
                (str(
                    type(e)),
                    e.args[0]))
            self.nagios_message.raise_status(
                NagiosMessage.NAGIOS_STATUS_UNKNOWN)
        finally:
            try:
                if self.driver and self.args.screenshot_path and os.path.isdir(self.args.screenshot_path):                
                    self.driver.save_screenshot(self.args.screenshot_path + '/selenium_' + datetime.now().strftime("%Y%m%d_%H%M%S") +'.png')
            except Exception:
                pass
            if self.driver:
                self.driver.quit()

            print(self.nagios_message)
            sys.exit(self.nagios_message.status_code)


class SelmonTestException(Exception):
    pass


class GlobalTimeoutException(Exception):
    pass


class ConnectionException(Exception):
    pass


class DriverInitException(Exception):
    pass
