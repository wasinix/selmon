# Selmon

## Origin
forked from objectified/selmon to get it working with Python3 and current selenium version

## Using Selenium Webdriver for Nagios Monitoring

<em>Note: when upgrading from 0.1 to 0.2, expect the API to break. On the upside: the new API is more sane.</em>

### Introduction
Selmon is a Python library for creating Nagios plugins that use real browsers, in order to be able to monitor web
applications easily. It does so by utilizing the great Selenium browser automation framework.
Selmon is the successor of Seymour (https://github.com/objectified/seymour). The main difference between the two is that
Selmon is based on the new Selenium implementation which is based on Webdriver, whereas Seymour was based on
Selenium 1/RC. Its implementation is fairly different, so the Webdriver implementation got a new name instead of just a
version bump. There are a couple of reasons why you might want to do monitoring using real browsers (or browser
engines), as opposed to writing scripts that simply perform HTTP requests and assert responses.
- Web applications become more complex in terms of front end technology, which makes it increasingly harder to
 analyse and simulate the actions of an application (ever tried to "script" monitoring for a GWT application?)
- An actual browser is the most representative way of simulating client actions - it's also the only way to include the
DOM in the monitoring process
- When browser compatibility breaks, you will notice
- Using automated browsers lets you test from a functional perspective, not a technical one; this means that the technical
implementation might change, but as long as the interface stays the same you're fine

### Requirements
* Python 3
* [Selenium Server](http://seleniumhq.org/download/) (this requires a compatible Java Runtime Environment to be installed)
* [Nagios](http://www.nagios.org) (or something that uses Nagios under the hood, like [Opsview](https://www.opsview.com))
* Appropriate browser drivers for use with the Selenium Server (for example: [ChromeDriver](https://code.google.com/p/selenium/wiki/ChromeDriver))

### Howto
I'm assuming you're already somewhat familiar with Python and Nagios/NRPE. If you want to give Selmon a quick spin,
you'll obviously need to install it. I prefer to use a virtualenv environment, I'm guessing you do too.

    $ git clone https://github.com/wasinix/selmon
    $ virtualenv selmon
    $ cd selmon
    $ python setup.py install

The next step is to download Selenium Server, and the appropriate drivers for various browsers. and start it
(see Requirements section above). Starting the Selenium Server with the Chrome driver is as easy as the following:

    $ java -Dwebdriver.chrome.driver=/path/to/chromedriver -jar selenium-server-standalone-2.25.0.jar

By default, the Selenium Server listens on port 4444. Let's create our first Selmon based Nagios plugin:


    #!/usr/bin/env python
    from selenium.webdriver.common.keys import Keys
    from selmon.nagios.plugin import Plugin
    from selmon.nagios.contextmanagers import benchmark, test
    
    
    class SeleniumHQMonitor(Plugin):
    
        def run(self):
            driver = self.driver
    
            with benchmark(self.nagios_message, 'open_homepage', warning=2):
                driver.get('http://www.seleniumhq.org/')
    
            search_elem = driver.find_element_by_name('q')
            search_elem.send_keys('python')
    
            with benchmark(self.nagios_message, 'submit_form'):
                search_elem.send_keys(Keys.RETURN)
    
            body_elem = driver.find_deferred_element_by_css_selector('body')
    
            with test(self.nagios_message, 'text present: python'):
                self.verify(driver.is_text_present_in_elem(body_elem, 'python'))
    
    
    monitor = SeleniumHQMonitor()
    monitor.start()



The plugin as written above retrieves http://www.seleniumhq.org/, types a query in the search field, submits the search form
and asserts that there are results in the resulting response. First let's see how the script can be used. Give it execute
permissions and run the following:

    $ ./selhq_monitor.py --help
    usage: selhq_monitor.py [-h] -H HOST -t TIMEOUT -b BROWSER

    optional arguments:
      -h, --help            show this help message and exit
      -H HOST, --host HOST  selenium webdriver remote host
      -t TIMEOUT, --timeout TIMEOUT
                            timeout in seconds to use for whole execution
      -b BROWSER, --browser BROWSER
                            browser to use, possible values: firefox,htmlunit_with
                            js,safari,ie,ipad,htmlunit,phantomjs,opera,chrome,ipho
                            ne,android

As you can see, the plugin we just created expects a few parameters.
* -H specifies the Selenium Server address and port to use
* -t specifies the global timeout for the entire run; when this timeout is exceeded during execution, the script will
 exit with a critical message
* -b specifies which browser to use; for possible values, consult the help message. In order to use one of the listed
browsers, you will need to plug the appropriate browser driver into the Selenium Server, and make sure the browser
is available on the machine on which the Selenium Server runs

We will go into details later, but first let's have a look at the script in action. Give the script execute permissions
to run on its own, and execute it with the following parameters.

    $ ./selhq_monitor.py -H http://localhost:4444/wd/hub -t 30 -b chrome
    OK: open_homepage executed in 2.47832202911 seconds, submit_form executed in 2.45883488655 seconds | 'open_homepage'=2.47832202911s;5;5;; 'submit_form'=2.45883488655s;3;5;;
    $ echo $?
    0

Here we executed the Nagios plugin that we just created, with parameters that indicate the URL/port of the Selenium
Server, set a global timeout of 30 seconds and specify that we want to execute our tests within Chrome. As you can see,
the plugin returns with a message, and has performance data appended to the message after a pipe character (\|), which
indicates the separation of a Nagios textual message and its performance data. Echoing its exit code, we can see that it
 returns 0, indicating that the test has been running successfully. In the case of a warning or error, the execution
  would have exited with an exit code of 1 (warning) or 2 (critical). You can play around with these values by changing
  the plugin's expectations. For example, you could change the text 'selenium' in the text verification statement to
  something that is unlikely to occur, for example: 'seleniummm'. Now let us look at the code.

As you can see, the newly created class inherits from the Plugin class in the selmon.nagios.plugin module, which takes care of most
things Nagios for us. The only thing left for us to do, is override its run() method and define the actual work for the
plugin we want to create. Within this run() method, we can get a reference to the underlying Selenium Driver object
(self.driver), which we can then use to write regular Selenium Webdriver code. In fact, we could just write
Webdriver code in the run() method and be done with it. But that's not all we want in a monitoring context. Selenium is
primarily used for functional web application testing, and for monitoring we probably have a few additional goals,
mostly centered around benchmarking response times and testing for certain conditions on which we will want to base the
output of the monitoring run. Where Selmon's predecessor, Seymour, used some magic for this (intercepting calls to the
driver and wrapping them in custom methods), this magic is gone in Selmon. Using Selmon, when you want to benchmark
a bunch of actions to be returned as performance data, you simply wrap them with the benchmark() context manager
available in selmon.nagios.contextmanagers. The code block that executes inside this context manager will be
timed, and the results will be become available as performance data in the Nagios output after script execution. When
 using the benchmark() context manager, we provide it with some information:

* a reference to the Nagios message object (self.nagios_message), so the context manager can add its performance data
 to it during the run
* a label, which it can use in the output and as the performance data label; this label will also be used for generating
graphs in Nagios
* optionally, pass warning and critical parameters, which indicate the number of seconds after which the Nagios message
should end up in warning or critical state. The defaults are 3 (warning) and 5 (critical)

A very common use case inside a monitoring run, is to verify whether a certain condition is true - and if it isn't,
generate a warning or critical message. If we were using Selenium as a functional test tool, this functionality would 
have been covered by the unit testing framework we were using to execute the Selenium runs. Here, we're not really using
a unit testing framework, so Selmon provides its own way to do this. As with the benchmark() context manager, Selmon also 
provides a contextmanager for these kinds of tests, surprisingly, called test(). It works very similar to benchmark(). 
Inside a call to the test() contextmanager, self.verify() can be used to verify a certain condition. self.verify() accepts
a boolean argument, and throws a SelmonTestException when the boolean evaluates to False. This makes sure that the test()
context manager can treat the Nagios object accordingly, add a message to it and set the correct Nagios exit code.

Another thing that is facilitated by extending the Plugin class is the retrieval of elements from the DOM that may not
 be immediately available, because the DOM might still be loading while the Webdriver client already tries to do its
 assertions. The Plugin class provides convenience methods for this to avoid too much complexity in  scripts that
 primarily serve as monitoring implementations. Since Ajax heavy web applications, where many assertions cannot be made
  by simply looking at the HTML source of a URL, are becoming more and more prevalent nowadays, one might appreciate
  easier ways to deal with such situations where all you want to do is check if an application is available. Check out
  the get_deferred_element_by_* methods in the Plugin class.

It is very likely that you'll want to use additional parameters for the Nagios plugin. Selmon provides a mechanism to do
this. By overriding the add_extra_args method, you can add additional parameters to the argument parser (which is an 
argparse.ArgumentParser instance). Here's a full example.

    #!/usr/bin/env python
    from selenium.webdriver.common.keys import Keys
    from selmon.nagios.plugin import Plugin
    from selmon.nagios.contextmanagers import benchmark, test
    
    
    class SeleniumHQMonitor(Plugin):
    
    
        def add_extra_args(self):
            self.arg_parser.add_argument('-f', '--file', 
                help='Some helpful message for inclusion in -h', required=True)
                
        def run(self):
            print "Hey, I've got an -f parameter too, its value is: %s" % self.args.file
            
            driver = self.driver
    
            with benchmark(self.nagios_message, 'open_homepage', warning=2):
                driver.get('http://www.seleniumhq.org/')
    
            search_elem = driver.find_element_by_name('q')
            search_elem.send_keys('python')
    
            with benchmark(self.nagios_message, 'submit_form'):
                search_elem.send_keys(Keys.RETURN)
    
            body_elem = driver.find_deferred_element_by_css_selector('body')
    
            with test(self.nagios_message, 'text present: python'):
                self.verify(driver.is_text_present_in_elem(body_elem, 'python'))
    
    
    monitor = SeleniumHQMonitor()
    monitor.start()


### Selmon in production
As you may have figured out by now, to use most browsers you will need a machine with a desktop/X to run these tests.
Your Nagios machine or Opsview masters/slaves probably don't have X installed (which is understandable), so I'd
recommend having a few dedicated (virtual) machines that run one or more Selenium Server instances, so that you can
point the Selmon based plugins to them through the -H parameter. If you'd like to keep these machines slim, you could
choose to use an in memory X server like Xvfb. In such a scenario, the Selmon Python module only needs to be installed
on the machines you run your tests from, not on the machine that carries out the actual tests. Lately, Selenium even
has support for PhantomJS, which does not require X at all. You can use that, if testing through the V8 engine is
sufficient for you.

### Known issues and shortcomings
Using a functional testing tool (Selenium) for an entirely different goal (monitoring) comes with a few consequences.
 There are a few things that are hard to do or even impossible when using Selenium. It's important to know about these.
* Selenium does not provide access to HTTP status codes; in other words, you won't know whether a page returns a status
code that lies in the 4xx/5xx range. To get around this, I suggest you check for the presence of elements on the page
* The performance data returned by Selmon is not entirely accurate, as the benchmarked code to provide performance data
includes the HTTP calls made to the Selenium Server to trigger the remote commands that are sent to a browser. While
these calls generally do not suffer from much overhead, it's important to know about this nuance when interpreting
performance data. In other words, any network latency and Selenium Server performance can distort your performance data.
