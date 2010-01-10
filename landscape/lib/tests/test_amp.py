from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList
from twisted.internet.protocol import ClientCreator
from twisted.internet.error import ConnectionDone

from landscape.lib.amp import (
    MethodCallError, MethodCall, MethodCallServerProtocol,
    MethodCallClientProtocol, MethodCallServerFactory,
    MethodCallClientFactory, RemoteObject, RemoteObjectCreator)
from landscape.tests.helpers import LandscapeTest


class Words(object):
    """Test class to be used as target object of a L{MethodCallProtocol}."""

    def secret(self):
        raise RuntimeError("I'm not supposed to be called!")

    def empty(self):
        pass

    def motd(self):
        return "Words are cool"

    def capitalize(self, word):
        return word.capitalize()

    def is_short(self, word):
        return len(word) < 4

    def concatenate(self, word1, word2):
        return word1 + word2

    def lower_case(self, word, index=None):
        if index is None:
            return word.lower()
        else:
            return word[:index] + word[index:].lower()

    def multiply_alphabetically(self, word_times):
        result = ""
        for word, times in sorted(word_times.iteritems()):
            result += word * times
        return result

    def meaning_of_life(self):

        class Complex(object):
            pass
        return Complex()

    def _check(self, word, seed, value=3):
        if seed == "cool" and value == 4:
            return "Guessed!"

    def guess(self, word, *args, **kwargs):
        return self._check(word, *args, **kwargs)

    def google(self, word):
        deferred = Deferred()
        if word == "Landscape":
            reactor.callLater(0.01, lambda: deferred.callback("Cool!"))
        elif word == "Easy query":
            deferred.callback("Done!")
        elif word == "Weird stuff":
            reactor.callLater(0.01, lambda: deferred.errback(Exception("bad")))
        elif word == "Censored":
            deferred.errback(Exception("very bad"))
        elif word == "Long query":
            # Do nothing, the deferred won't be fired at all
            pass
        return deferred


class WordsServerProtocol(MethodCallServerProtocol):

    methods = ["empty",
               "motd",
               "capitalize",
               "is_short",
               "concatenate",
               "lower_case",
               "multiply_alphabetically",
               "translate",
               "meaning_of_life",
               "guess",
               "google"]


class WordsClientProtocol(MethodCallClientProtocol):

    timeout = 0.1


class WordsServerFactory(MethodCallServerFactory):

    protocol = WordsServerProtocol


class WordsClientFactory(MethodCallClientFactory):

    protocol = WordsClientProtocol
    factor = 0.19


class RemoteWordsCreator(RemoteObjectCreator):

    factory = WordsClientFactory


class MethodCallProtocolTest(LandscapeTest):

    def setUp(self):
        super(MethodCallProtocolTest, self).setUp()
        socket = self.mktemp()
        factory = WordsServerFactory(Words())
        self.port = reactor.listenUNIX(socket, factory)

        def set_protocol(protocol):
            self.protocol = protocol

        connector = ClientCreator(reactor, WordsClientProtocol)
        connected = connector.connectUNIX(socket)
        return connected.addCallback(set_protocol)

    def tearDown(self):
        self.protocol.transport.loseConnection()
        self.port.stopListening()
        super(MethodCallProtocolTest, self).tearDown()

    def test_with_forbidden_method(self):
        """
        If a method is not included in L{MethodCallProtocol.methods} it
        can't be called.
        """
        result = self.protocol.callRemote(MethodCall,
                                          method="secret",
                                          args=[],
                                          kwargs={})
        return self.assertFailure(result, MethodCallError)

    def test_with_no_arguments(self):
        """
        A connected client can issue a L{MethodCall} without arguments and
        with an empty response.
        """
        result = self.protocol.callRemote(MethodCall,
                                          method="empty",
                                          args=[],
                                          kwargs={})
        return self.assertSuccess(result, {"result": None,
                                           "deferred": None})

    def test_with_return_value(self):
        """
        A connected client can issue a L{MethodCall} targeted to an
        object method with a return value.
        """
        result = self.protocol.callRemote(MethodCall,
                                          method="motd",
                                          args=[],
                                          kwargs={})
        return self.assertSuccess(result, {"result": "Words are cool",
                                           "deferred": None})

    def test_with_one_argument(self):
        """
        A connected AMP client can issue a L{MethodCall} with one argument and
        a response value.
        """
        result = self.protocol.callRemote(MethodCall,
                                          method="capitalize",
                                          args=["john"],
                                          kwargs={})
        return self.assertSuccess(result, {"result": "John",
                                           "deferred": None})

    def test_with_boolean_return_value(self):
        """
        The return value of a L{MethodCall} argument can be a boolean.
        """
        result = self.protocol.callRemote(MethodCall,
                                          method="is_short",
                                          args=["hi"],
                                          kwargs={})
        return self.assertSuccess(result, {"result": True,
                                           "deferred": None})

    def test_with_many_arguments(self):
        """
        A connected client can issue a L{MethodCall} with many arguments.
        """
        result = self.protocol.callRemote(MethodCall,
                                          method="concatenate",
                                          args=["You ", "rock"],
                                          kwargs={})
        return self.assertSuccess(result, {"result": "You rock",
                                           "deferred": None})

    def test_with_default_arguments(self):
        """
        A connected client can issue a L{MethodCall} for methods having
        default arguments.
        """
        result = self.protocol.callRemote(MethodCall,
                                          method="lower_case",
                                          args=["OHH"],
                                          kwargs={})
        return self.assertSuccess(result, {"result": "ohh",
                                           "deferred": None})

    def test_with_overriden_default_arguments(self):
        """
        A connected client can issue a L{MethodCall} with keyword arguments
        having default values in the target object.  If a value is specified by
        the caller it will be used in place of the default value
        """
        result = self.protocol.callRemote(MethodCall,
                                          method="lower_case",
                                          args=["OHH"],
                                          kwargs={"index": 2})
        return self.assertSuccess(result, {"result": "OHh",
                                           "deferred": None})

    def test_with_dictionary_arguments(self):
        """
        Method arguments passed to a L{MethodCall} can be dictionaries.
        """
        result = self.protocol.callRemote(MethodCall,
                                          method="multiply_alphabetically",
                                          args=[{"foo": 2, "bar": 3}],
                                          kwargs={})
        return self.assertSuccess(result, {"result": "barbarbarfoofoo",
                                           "deferred": None})

    def test_with_non_serializable_return_value(self):
        """
        If the target object method returns an object that can't be serialized,
        the L{MethodCall} result is C{None}.
        """
        result = self.protocol.callRemote(MethodCall,
                                          method="meaning_of_life",
                                          args=[],
                                          kwargs={})
        return self.assertFailure(result, MethodCallError)


class RemoteObjectTest(LandscapeTest):

    def setUp(self):
        super(RemoteObjectTest, self).setUp()
        socket = self.mktemp()
        server_factory = WordsServerFactory(Words())
        self.port = reactor.listenUNIX(socket, server_factory)

        def set_remote(protocol):
            self.protocol = protocol
            self.words = RemoteObject(protocol)
            client_factory.stopTrying()

        connected = Deferred()
        connected.addCallback(set_remote)
        client_factory = WordsClientFactory(reactor)
        client_factory.notifier = connected.callback
        reactor.connectUNIX(socket, client_factory)
        return connected

    def tearDown(self):
        self.protocol.transport.loseConnection()
        self.port.stopListening()
        super(RemoteObjectTest, self).tearDown()

    def test_method_call_sender_with_forbidden_method(self):
        """
        A L{RemoteObject} can send L{MethodCall}s without arguments and withj
        an empty response.
        """
        result = self.words.secret()
        return self.assertFailure(result, MethodCallError)

    def test_with_no_arguments(self):
        """
        A L{RemoteObject} can send L{MethodCall}s without arguments and withj
        an empty response.
        """
        return self.assertSuccess(self.words.empty())

    def test_with_return_value(self):
        """
        A L{RemoteObject} can send L{MethodCall}s without arguments and get
        back the value of the commands's response.
        """
        result = self.words.motd()
        return self.assertSuccess(result, "Words are cool")

    def test_with_one_argument(self):
        """
        A L{RemoteObject} can send L{MethodCall}s with one argument and get
        the response value.
        """
        result = self.words.capitalize("john")
        return self.assertSuccess(result, "John")

    def test_with_one_keyword_argument(self):
        """
        A L{RemoteObject} can send L{MethodCall}s with a named argument.
        """
        result = self.words.capitalize(word="john")
        return self.assertSuccess(result, "John")

    def test_with_boolean_return_value(self):
        """
        The return value of a L{MethodCall} argument can be a boolean.
        """
        return self.assertSuccess(self.words.is_short("hi"), True)

    def test_with_many_arguments(self):
        """
        A L{RemoteObject} can send L{MethodCall}s with more than one argument.
        """
        result = self.words.concatenate("You ", "rock")
        return self.assertSuccess(result, "You rock")

    def test_with_many_keyword_arguments(self):
        """
        A L{RemoteObject} can send L{MethodCall}s with several
        named arguments.
        """
        result = self.words.concatenate(word2="rock", word1="You ")
        return self.assertSuccess(result, "You rock")

    def test_with_default_arguments(self):
        """
        A L{RemoteObject} can send a L{MethodCall} having an argument with
        a default value.
        """
        result = self.words.lower_case("OHH")
        return self.assertSuccess(result, "ohh")

    def test_with_overriden_default_arguments(self):
        """
        A L{RemoteObject} can send L{MethodCall}s overriding the default
        value of an argument.
        """
        result = self.words.lower_case("OHH", 2)
        return self.assertSuccess(result, "OHh")

    def test_with_dictionary_arguments(self):
        """
        A L{RemoteObject} can send a L{MethodCall}s for methods requiring
        a dictionary arguments.
        """
        result = self.words.multiply_alphabetically({"foo": 2, "bar": 3})
        return self.assertSuccess(result, "barbarbarfoofoo")

    def test_with_generic_args_and_kwargs(self):
        """
        A L{RemoteObject} behaves well with L{MethodCall}s for methods
        having generic C{*args} and C{**kwargs} arguments.
        """
        result = self.words.guess("word", "cool", value=4)
        return self.assertSuccess(result, "Guessed!")

    def test_with_success_full_deferred(self):
        """
        If the target object method returns a L{Deferred}, it is handled
        transparently.
        """
        result = self.words.google("Landscape")
        return self.assertSuccess(result, "Cool!")

    def test_with_failing_deferred(self):
        """
        If the target object method returns a failing L{Deferred}, a
        L{MethodCallError} is raised.
        """
        result = self.words.google("Weird stuff")
        return self.assertFailure(result, MethodCallError)

    def test_with_already_callback_deferred(self):
        """
        The target object method can return an already fired L{Deferred}.
        """
        result = self.words.google("Easy query")
        return self.assertSuccess(result, "Done!")

    def test_with_already_errback_deferred(self):
        """
        If the target object method can return an already failed L{Deferred}.
        """
        result = self.words.google("Censored")
        return self.assertFailure(result, MethodCallError)

    def test_with_deferred_timeout(self):
        """
        If the peer protocol doesn't send a response for a deferred within
        the given timeout, the method call fails.
        """
        result = self.words.google("Long query")
        return self.assertFailure(result, MethodCallError)


class MethodCallClientFactoryTest(LandscapeTest):

    def setUp(self):
        super(MethodCallClientFactoryTest, self).setUp()
        self.socket = self.mktemp()
        self.server_factory = WordsServerFactory(Words())

    def test_connect_with_retry(self):
        """
        The L{MethodCallClientFactory} keeps trying connecting till it
        succeeds.
        """
        connected = Deferred()
        client_factory = WordsClientFactory(reactor)
        client_factory.notifier = connected.callback

        ports = []

        def listen():
            self.assertTrue(client_factory.retries > 0)
            ports.append(reactor.listenUNIX(self.socket, self.server_factory))

        def assert_connection(protocol):
            self.assertTrue(isinstance(protocol, WordsClientProtocol))
            client_factory.stopTrying()
            protocol.transport.loseConnection()
            ports[0].stopListening()

        reactor.callLater(0.2, listen)
        reactor.connectUNIX(self.socket, client_factory)
        return connected.addCallback(assert_connection)

    def test_reconnect(self):
        """
        The L{MethodCallClientFactory} reconnects automatically if the
        connection drops, and calls the notifier function again.
        """
        ports = [reactor.listenUNIX(self.socket, self.server_factory)]
        protocols = []
        reconnected = Deferred()

        def restart_listening():
            ports.append(reactor.listenUNIX(self.socket, self.server_factory))

        def connection_made(protocol):
            if len(ports) == 1:
                # First connection
                self.assertTrue(client_factory.retries == 0)
                protocols.append(protocol)
                protocol.transport.loseConnection()
                ports[0].stopListening()
                reactor.callLater(0.1, restart_listening)
            else:
                # Second connection
                self.assertEquals(client_factory.delay,
                                  client_factory.initialDelay)
                self.assertIsNot(protocol, protocols[0])
                client_factory.stopTrying()
                protocol.transport.loseConnection()
                ports[1].stopListening()
                reconnected.callback(None)

        client_factory = WordsClientFactory(reactor)
        client_factory.notifier = connection_made
        reactor.connectUNIX(self.socket, client_factory)
        return reconnected


class RemoteObjectCreatorTest(LandscapeTest):

    def setUp(self):
        super(RemoteObjectCreatorTest, self).setUp()
        self.socket = self.mktemp()
        self.server_factory = WordsServerFactory(Words())
        self.port = reactor.listenUNIX(self.socket, self.server_factory)
        self.connector = RemoteWordsCreator(reactor, self.socket,
                                            retry_on_reconnect=True,
                                            timeout=0.7)

        def set_remote(words):
            self.words = words

        connected = self.connector.connect()
        return connected.addCallback(set_remote)

    def tearDown(self):
        self.connector.disconnect()
        self.port.stopListening()
        super(RemoteObjectCreatorTest, self).tearDown()

    def test_connect(self):
        """
        The L{RemoteObject} resulting form the deferred returned by
        L{RemoteObjectCreator.connect} is properly connected to the
        remote peer.
        """
        return self.assertSuccess(self.words.empty())

    def test_reconnect(self):
        """
        If the connection is lost, the L{RemoteObject} created by the creator
        will transparently handle the reconnection.
        """
        self.words._protocol.transport.loseConnection()
        self.port.stopListening()

        def restart_listening():
            self.port = reactor.listenUNIX(self.socket, self.server_factory)
            reactor.callLater(0.3, assert_remote)

        def assert_remote():
            result = self.words.empty()
            result.addCallback(lambda x: reconnected.callback(None))
            return result

        reactor.callLater(0.01, restart_listening)
        reconnected = Deferred()
        return reconnected

    def test_method_call_error(self):
        """
        If a L{MethodCall} fails due to a L{MethodCallError}, the
        L{RemoteObject} won't try to perform it again.
        """
        return self.assertFailure(self.words.secret(), MethodCallError)

    def test_retry(self):
        """
        If the connection is lost, the L{RemoteObject} created by the creator
        will transparently retry to perform the L{MethodCall} requests that
        failed due to the broken connection.
        """
        self.words._protocol.transport.loseConnection()
        self.port.stopListening()

        def restart_listening():
            self.port = reactor.listenUNIX(self.socket, self.server_factory)

        reactor.callLater(0.1, restart_listening)
        return self.words.empty()

    def test_retry_with_method_call_error(self):
        """
        If a retried L{MethodCall} request fails due to a L{MethodCallError},
        the L{RemoteObject} will properly propagate the error to the original
        caller.
        """
        self.words._protocol.transport.loseConnection()
        self.port.stopListening()

        def restart_listening():
            self.port = reactor.listenUNIX(self.socket, self.server_factory)

        def assert_failure(error):
            self.assertEquals(str(error), "Forbidden method 'secret'")

        reactor.callLater(0.5, restart_listening)
        result = self.words.secret()
        self.assertFailure(result, MethodCallError)
        return result.addCallback(assert_failure)

    def test_wb_retry_with_while_still_disconnected(self):
        """
        The L{RemoteObject._retry} method gets called as soon as a new
        connection is ready, but even in case for whatever reason the
        connection drops again very quickly, the C{_retry} method will
        behave as expected.
        """
        self.words._protocol.transport.loseConnection()
        self.port.stopListening()

        def handle_reconnect(protocol):
            # In this precise moment we have a newly connected protocol
            self.words._protocol = protocol

            # Pretend that the connection is lost very quickly
            protocol.transport.loseConnection()
            self.port.stopListening()

            # Force RemoteObject._retry to run using a disconnected protocol
            reactor.callLater(0, self.words._retry)

            # Restore the real handler and start listening again very soon
            self.connector._factory.notifier = self.words._handle_reconnect
            reactor.callLater(0.2, restart_listening)

        def restart_listening():
            self.port = reactor.listenUNIX(self.socket, self.server_factory)

        def assert_failure(error):
            self.assertEquals(str(error), "Forbidden method 'secret'")

        self.connector._factory.notifier = handle_reconnect
        reactor.callLater(0.2, restart_listening)
        result = self.words.secret()
        self.assertFailure(result, MethodCallError)
        return result.addCallback(assert_failure)

    def test_retry_with_many_method_calls(self):
        """
        If several L{MethodCall} requests were issued while disconnected, they
        will be all eventually completed when the connection gets established
        again.
        """
        self.words._protocol.transport.loseConnection()
        self.port.stopListening()

        def restart_listening():
            self.port = reactor.listenUNIX(self.socket, self.server_factory)

        def assert_guess(response):
            self.assertEquals(response, "Guessed!")

        def assert_secret(failure):
            self.assertEquals(str(failure.value), "Forbidden method 'secret'")

        def assert_motd(response):
            self.assertEquals(response, "Words are cool")

        reactor.callLater(0.1, restart_listening)

        results = [self.words.guess("word", "cool", value=4),
                   self.words.secret(),
                   self.words.motd()]
        results[0].addCallback(assert_guess)
        results[1].addErrback(assert_secret)
        results[2].addCallback(assert_motd)
        return DeferredList(results)

    def test_retry_without_retry_on_reconnect(self):
        """
        If C{retry_on_reconnect} is C{False}, the L{RemoteObject} object won't
        retry to perform requests which failed because the connection was
        lost, however requests made after a reconnection will still succeed.
        """
        self.words._protocol.transport.loseConnection()
        self.port.stopListening()

        def restart_listening():
            self.port = reactor.listenUNIX(self.socket, self.server_factory)
            reactor.callLater(0.3, assert_reconnected)

        def assert_reconnected():
            result = self.words.empty()
            result.addCallback(lambda x: reconnected.callback(None))
            return result

        reactor.callLater(0.1, restart_listening)
        self.words._retry_on_reconnect = False
        result = self.words.empty()
        self.assertFailure(result, ConnectionDone)
        reconnected = Deferred()
        return result.addCallback(lambda x: reconnected)

    def test_retry_with_timeout(self):
        """
        If a C{timeout} is set, the L{RemoteObject} object will errback failed
        L{MethodCall}s after that amount of seconds, without retrying them when
        the connection established again.
        """
        self.words._protocol.transport.loseConnection()
        self.port.stopListening()

        def restart_listening():
            self.port = reactor.listenUNIX(self.socket, self.server_factory)
            reactor.callLater(0.1, reconnected.callback, None)

        def assert_failure(error):
            self.assertEquals(str(error), "timeout")
            return reconnected

        reactor.callLater(0.9, restart_listening)
        result = self.words.empty()
        self.assertFailure(result, MethodCallError)
        reconnected = Deferred()
        return result.addCallback(assert_failure)
