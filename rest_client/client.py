"""Thin REST/JSON client based on Requests."""

from urlparse import urlsplit, urlunsplit
import json
import logging
import posixpath

import requests

from requests.exceptions import RequestException, HTTPError

log = logging.getLogger(__name__)


# TODO: decide to support query params in base_url or not. Simplify _url_join.
# TODO: ServiceClient() -> configure from settings and provide call_project()

class RestClient(object):

    """Thin REST/JSON client based on Requests."""

    def __init__(self, base_url, auth=None, options=None, user_agent=None):
        """Create a new RestClient instance.

        Args:

            base_url (str): Base URL used to form the final url of all requests
                sent with this instance of RestClient.

            auth (Optional[tuple|callable]): Enable Basic/Digest/Custom HTTP
                Auth.

            options (Optional[dict]): Default keyword arguments applied to all
                requests sent with this RestClient.

            user_agent (Optional[str]): Set the User-Agent header of all
                requests sent with this instance of RestClient.

        Notes:

            - Redirect are considered failure
        """
        self.base_url = base_url
        self.default_options = {'allow_redirects': False}
        if options is not None:
            self.default_options.update(options)

        # Detect requests version 1.X
        self.requests_legacy = requests.__version__[0] == '1'

        self.session = requests.Session()
        self.session.auth = auth
        if user_agent is not None:
            user_agent += ' requests/%s' % requests.__version__
            self.session.headers.update({'User-Agent': user_agent})

        # Accept only JSON responses
        self.session.headers.update({'Accept': 'application/json'})

    def _url_join(self, base, *args):
        """Join an arbitrary number of URL path segments together."""
        scheme, netloc, path, query, fragment = urlsplit(base)
        path = path if len(path) else '/'
        path = posixpath.join(path, *[str(x) for x in args])
        return urlunsplit([scheme, netloc, path, query, fragment])

    def call(self, method, segments, **kwargs):
        """Initiate a REST request.

        Args:

            method (str): method for the new request.

            segments (tuple|list): segments of the URL.

            **kwargs: Keyword arguments passed directly to requests.

        Original args of Requests v2.7:

            params (dict|bytes): params to be sent in the query string of the
                request.

            data: Dictionary or bytes to send in the body of the request.

            json: json to send in the body of the request.

            headers (dict|MultiDict): HTTP Headers to send with the request.

            cookies (dict|CookieJar): Cookies to send with the request.

            files (dict): Dictionary of ``'filename': file-like-objects``
                for multipart encoding upload.

            auth (tuple|callable): Enable Basic/Digest/Custom HTTP Auth.

            timeout (float|tuple): How long to wait for the server to send data
                before giving up, as a float, or a
                (connect timeout, read timeout) tuple.

            allow_redirects (bool): Follow or ignore the redirect in responses.

            proxies: Dictionary mapping protocol to the URL of the proxy.

            stream (bool): whether to immediately download the response
                content.

            verify: if True, the SSL cert will be verified. A CA_BUNDLE path
                can also be provided.

            cert: if String, path to ssl client cert file (.pem). If Tuple,
                ('cert', 'key') pair.

        Returns:
            An original request.Response object.
        """
        if not (isinstance(segments, tuple) or isinstance(segments, list)):
            raise TypeError("segments argument must be a tuple or a list")

        url = self._url_join(self.base_url, *segments)

        # Requests 1.x didn't support json natively
        if self.requests_legacy and 'json' in kwargs:
            # 1. Serialize JSON payload
            kwargs['data'] = json.dumps(kwargs.pop('json'))
            # 2. Set Content-Type
            headers = kwargs.setdefault('headers', {})
            headers.update({'Content-Type': 'application/json'})

        opts = self.default_options.copy()
        opts.update(kwargs)

        log.debug('RestClient %s %s params=%s', method, url, opts)

        # Perform the HTTP call
        try:
            resp = self.session.request(method=method, url=url, **opts)
        except RequestException as exc:
            error = exc.__class__.__name__
            errorlog('failure', error, method, url, exc)
            raise

        # For now: treat redirect as a failure
        if resp.is_redirect:
            errorlog('redirect', 'redirect', method, url,
                     resp.headers['location'], status=resp.status_code,
                     body=resp.content)
            raise IOError('Redirect(%s) %s' % (resp.status_code, resp.reason))

        # Let python-requests detect errors
        # We want the original request exception to keep the same API
        try:
            resp.raise_for_status()
        except HTTPError:
            error_type, error, message = error_from_response(resp)
            errorlog(error_type, error, method, url, message,
                     status=resp.status_code, body=resp.content)
            raise

        log.debug('RestClient %s %s got: %s %s',
                  method, url, resp.status_code, resp.content)

        return resp


def errorlog(type, error, method, url, detail, status=None, body=None):
    """Produce standard error log.

    Example:

        RESTClient type=<> error=<> msg="<>" req="METHOD /<>" [status=<>]
        <body>
    """
    line = 'RESTClient type=%s error=%s detail="%s" req="%s %s"' % (
        type, error, detail, method, url)
    if status is not None:
        line += ' status=%s' % status
    if body is not None:
        line += '\n%s' % body
    log.error(line)


def error_from_response(resp):
    """Classify client/server error and extract error payload (failsafe).

    Expected payload:

    {
        "error": "TypeOfError",
        "message": "Details about this error"
    }
    """
    error_type = 'client' if resp.status_code < 500 else 'server'

    try:
        payload = resp.json()
    except:
        payload = {}
    finally:
        error = payload.get("error", "-")
        message = payload.get("message", "-")

    return error_type, error, message
