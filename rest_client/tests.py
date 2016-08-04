import base64
import unittest

from nose_parameterized import parameterized
import httpretty
import mock


class TestBase(unittest.TestCase):

    TEST_BASE = 'http://host/base'
    TEST_BODY = 'MyBodyIsACage'

    def assert_header(self, request, name, value):
        self.assertIn(name, request.headers)
        self.assertEqual(request.headers[name], value)


class TestClientInstance(TestBase):

    def test_session_simple(self):
        from rest_client import RestClient
        import requests
        client = RestClient('http://host/base')
        self.assertIsInstance(client.session, requests.Session)
        self.assertEqual(client.default_options, {'allow_redirects': False})

    def test_session_auth(self):
        from rest_client import RestClient
        auth = ('U', 'P')
        client = RestClient('http://host/base', auth=auth)
        self.assertEqual(client.session.auth, auth)

    def test_session_user_agent(self):
        from rest_client import RestClient
        user_agent = 'Poipoi/1.0'
        client = RestClient('http://host/base', user_agent=user_agent)

        self.assertIn('User-Agent', client.session.headers)
        self.assertIn(user_agent, client.session.headers['User-Agent'])

    def test_options(self):
        from rest_client import RestClient
        options = {'Key': 'Value'}
        client = RestClient('http://host/base', options=options)
        self.assertEqual(client.default_options,
                         {'allow_redirects': False, 'Key': 'Value'})


@mock.patch('rest_client.client.log')
class TestErrorLog(TestBase):

    def test_nominal(self, m_log):
        from rest_client.client import errorlog
        errorlog('TYPE', 'ERROR', 'METHOD', 'URL', 'DETAILS')

        m_log.error.assert_called_once_with(
            'RESTClient type=TYPE error=ERROR detail="DETAILS" '
            'req="METHOD URL"')

    def test_status(self, m_log):
        from rest_client.client import errorlog
        errorlog('TYPE', 'ERROR', 'METHOD', 'URL', 'DETAILS', 400)

        m_log.error.assert_called_once_with(
            'RESTClient type=TYPE error=ERROR detail="DETAILS" '
            'req="METHOD URL" status=400')

    def test_body(self, m_log):
        from rest_client.client import errorlog
        errorlog('TYPE', 'ERROR', 'METHOD', 'URL', 'DETAILS', body='BODY')

        m_log.error.assert_called_once_with(
            'RESTClient type=TYPE error=ERROR detail="DETAILS" '
            'req="METHOD URL"\nBODY')


@mock.patch('rest_client.client.errorlog')
class TestError(TestBase):

    def test_exception(self, m_errorlog):
        from rest_client import RestClient, RequestException

        client = RestClient(self.TEST_BASE)
        with mock.patch.object(client, 'session') as m_session:
            m_request = m_session.request
            m_request.side_effect = RequestException()

            with self.assertRaises(RequestException):
                client.call('GET', ())

        m_errorlog.assert_called_once_with(
            'failure', 'RequestException', 'GET', 'http://host/base',
            m_request.side_effect)

    def test_client_error(self, m_errorlog):
        from rest_client import RestClient, HTTPError

        client = RestClient(self.TEST_BASE)
        with mock.patch.object(client, 'session') as m_session:
            m_response = m_session.request.return_value
            m_response.is_redirect = False
            m_response.raise_for_status.side_effect = HTTPError()
            m_response.status_code = 400
            m_response.json.return_value = {'error': 'ERROR', 'message': 'MSG'}

            with self.assertRaises(HTTPError):
                client.call('GET', ())

        m_errorlog.assert_called_once_with(
            'client', 'ERROR', 'GET', 'http://host/base', 'MSG',
            body=m_response.content, status=400)

    def test_server_error(self, m_errorlog):
        from rest_client import RestClient, HTTPError

        client = RestClient(self.TEST_BASE)
        with mock.patch.object(client, 'session') as m_session:
            m_response = m_session.request.return_value
            m_response.is_redirect = False
            m_response.raise_for_status.side_effect = HTTPError()
            m_response.status_code = 500
            m_response.json.return_value = {'error': 'ERROR', 'message': 'MSG'}

            with self.assertRaises(HTTPError):
                client.call('GET', ())

        m_errorlog.assert_called_once_with(
            'server', 'ERROR', 'GET', 'http://host/base', 'MSG',
            body=m_response.content, status=500)

    def test_redirect(self, m_errorlog):
        from rest_client import RestClient

        client = RestClient(self.TEST_BASE)
        with mock.patch.object(client, 'session') as m_session:
            m_response = m_session.request.return_value
            m_response.is_redirect = True
            m_response.status_code = 301
            m_response.json.return_value = {'error': 'ERROR', 'message': 'MSG'}
            m_response.headers = {'location': 'LOCATION'}
            with self.assertRaises(IOError):
                client.call('GET', ())

        m_errorlog.assert_called_once_with(
            'redirect', 'redirect', 'GET', 'http://host/base', 'LOCATION',
            body=m_response.content, status=301)


class TestApi(TestBase):

    def test_segment_type(self):
        from rest_client import RestClient

        client = RestClient(self.TEST_BASE)
        with self.assertRaises(TypeError):
            client.call('GET', 'thisIsNotATupleOrList')


class TestLegacyRequest(TestBase):

    def test_legacy(self):
        from rest_client import RestClient

        client = RestClient(self.TEST_BASE)
        client.requests_legacy = True  # Force detection of requests 1.x

        with mock.patch.object(client, 'session') as m_session:
            m_response = m_session.request.return_value
            m_response.is_redirect = False
            m_response.status_code = 200

            client.call('GET', [], json='[1, 2, 3]')

            m_session.request.assert_called_once_with(
                allow_redirects=False, data='"[1, 2, 3]"',
                headers={'Content-Type': 'application/json'}, method='GET',
                url='http://host/base')


class TestClientFunctional(TestBase):

    TEST_BASE = 'http://host/base'
    TEST_BODY = 'MyBodyIsACage'

    def setUp(self):
        httpretty.enable()
        httpretty.register_uri('GET', self.TEST_BASE, status=200,
                               body=self.TEST_BODY)

    def tearDown(self):
        httpretty.reset()

    def test_request(self):
        from rest_client import RestClient
        RestClient(self.TEST_BASE).call('GET', ())
        req = httpretty.last_request()

        self.assertEqual(req.path, '/base')
        self.assertEqual(req.body, b'')
        self.assertEqual(req.method, 'GET')
        self.assertEqual(req.request_version, 'HTTP/1.1')

    def test_headers(self):
        from rest_client import RestClient
        RestClient(self.TEST_BASE).call('GET', ())
        req = httpretty.last_request()

        self.assert_header(req, 'host', 'host')
        self.assert_header(req, 'connection', 'keep-alive')
        self.assert_header(req, 'accept', 'application/json')
        self.assert_header(req, 'accept-encoding', 'gzip, deflate')

    def test_response(self):
        from rest_client import RestClient
        response = RestClient(self.TEST_BASE).call('GET', ())

        import requests
        self.assertIsInstance(response, requests.Response)
        self.assertEqual(response.text, self.TEST_BODY)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.url, self.TEST_BASE)

    def test_response_redirect(self):
        headers = {'Location': 'http://go-away.com'}
        httpretty.register_uri('GET', self.TEST_BASE, status=301,
                               adding_headers=headers)

        from rest_client import RestClient

        with self.assertRaises(IOError):
            RestClient(self.TEST_BASE).call('GET', ())

    def test_response_client_error(self):
        httpretty.register_uri('GET', self.TEST_BASE, status=400)

        from rest_client import RestClient, HTTPError

        with self.assertRaises(HTTPError):
            RestClient(self.TEST_BASE).call('GET', ())

    def test_response_server_error(self):
        httpretty.register_uri('GET', self.TEST_BASE, status=500)

        from rest_client import RestClient, HTTPError

        with self.assertRaises(HTTPError):
            RestClient(self.TEST_BASE).call('GET', ())

    @parameterized.expand(['HEAD', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
    def test_method(self, method):
        httpretty.register_uri(method, self.TEST_BASE, status=200)

        from rest_client import RestClient
        RestClient(self.TEST_BASE).call(method, ())
        req = httpretty.last_request()

        self.assertEqual(req.method, method)

    def test_auth(self):
        from rest_client import RestClient
        auth = ('user_name', 'password')
        RestClient(self.TEST_BASE, auth=auth).call('GET', ())
        req = httpretty.last_request()

        auth = base64.b64encode(b'user_name:password').decode('utf-8')
        self.assert_header(req, 'authorization', 'Basic %s' % auth)

    @parameterized.expand([
        ('/base', []),
        ('/base/elements', ['elements']),
        ('/base/elements/1', ['elements', 1]),
        ])
    def test_segment(self, path, segments):
        httpretty.register_uri('GET', 'http://host%s' % path, status=200)

        from rest_client import RestClient
        RestClient(self.TEST_BASE).call('GET', segments)
        req = httpretty.last_request()

        self.assertEqual(req.path, path)
