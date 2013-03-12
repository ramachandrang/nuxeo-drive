"""Common Nuxeo Automation client utilities."""

import sys
import platform
import base64
import json
import urlparse
import mimetypes
import random
import time
from datetime import datetime
import urllib
import urllib2
from urllib import urlencode
from urllib2 import HTTPHandler, HTTPSHandler
from urllib2 import HTTPRedirectHandler
from urllib2 import ProxyBasicAuthHandler
from urllib2 import HTTPPasswordMgr
from cookielib import CookieJar
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart

from nxdrive.logging_config import get_logger
from nxdrive.client.common import DEFAULT_IGNORED_PREFIXES
from nxdrive.client.common import DEFAULT_IGNORED_SUFFIXES
from nxdrive.utils import create_settings
from nxdrive.utils import classproperty
from nxdrive.utils import ProxyConnectionError, ProxyConfigurationError
from nxdrive.utils import get_maintenance_message
from nxdrive import Constants
from nxdrive import DEBUG, DEBUG_QUOTA_EXCEPTION, DEBUG_MAINTENANCE_EXCEPTION

log = get_logger(__name__)


DEVICE_DESCRIPTIONS = {
    'linux2': 'Linux Desktop',
    'darwin': 'Mac OSX Desktop',
    'cygwin': 'Windows Desktop',
    'win32': 'Windows Desktop',
}


class Unauthorized(Exception):

    def __init__(self, url, user_id, code = 401, data = ''):
        self.url = url
        self.user_id = user_id
        self.code = code
        self.data = data

    def __str__(self):
        return (_("'%s' is not authorized to access '%s' with"
                " the provided credentials. http code=%d, data=%s") % (self.user_id, self.url, self.code, str(self.data)))

class QuotaExceeded(Exception):
    def __init__(self, url, user_id, ref, size):
        self.url = url
        self.user_id = user_id
        self.ref = ref
        self.size = size

    def __str__(self):
        return (_("'%s' exceeded quota for '%s' when"
                " storing document %s") % (self.user_id, self.url, self.ref))

class MaintenanceMode(Exception):
    def __init__(self, url, user_id, retry_after, schedules):
        self.url = url
        self.user_id = user_id
        self.retry_after = retry_after
        if schedules is not None:
            status = schedules['Status']
            if len(schedules['ScheduleItems']) == 1:
                schedule = schedules['ScheduleItems'][0]
            else:
                schedule = None
            self.msg, self.detail, self.data1, self.data2 = get_maintenance_message(status, schedule = schedule)
        else:
            self.msg, self.detail, self.data1, self.data2 = get_maintenance_message('maintenance')

    def __str__(self):
        return '\n'.join((self.msg, self.detail))

class ProxyInfo(object):
    """Holder class for proxy information"""

    PORT = '8090'
    PORT_INTEGER = int(PORT)
    PROXY_SERVER = 'server'
    PROXY_AUTODETECT = 'autodetect'
    PROXY_DIRECT = 'direct'

    def __init__(self, autodetect = False, server_url = None, port = None, authn_required = False, user = None, pwd = None):
        self.autodetect = autodetect
        if self.autodetect:
            return

        self.authn_required = authn_required
        if authn_required and not user:
            raise ProxyConfigurationError('missing username')

        self.user = user
        self.pwd = pwd
        if not server_url is None and not port:
            raise ProxyConfigurationError('missing server or port')

        self.server_url = server_url
        self.port = port

    @staticmethod
    def get_proxy():
        settings = create_settings()
        if settings is None:
            return None

        useProxy = settings.value('preferences/useProxy', ProxyInfo.PROXY_DIRECT)
        if useProxy == ProxyInfo.PROXY_DIRECT:
            return None
        elif useProxy == ProxyInfo.PROXY_AUTODETECT:
            return ProxyInfo(autodetect = True)
        elif useProxy == ProxyInfo.PROXY_SERVER:
            server = settings.value('preferences/proxyServer')
            if not server:
                # short-circuit the initialialization
                return None
            else:
                user = settings.value('preferences/proxyUser')
                pwd = settings.value('preferences/proxyPwd')

                if sys.platform == 'win32':
                    authnAsString = settings.value('preferences/proxyAuthN', 'false')
                    if authnAsString.lower() == 'true':
                        authN = True
                    elif authnAsString.lower() == 'false':
                        authN = False
                    else:
                        authN = False
                    try:
                        port = settings.value('preferences/proxyPort', ProxyInfo.PORT)
                        port = int(port)
                    except ValueError:
                        port = 0

                else:
                    authN = settings.value('preferences/proxyAuthN', False)
                    port = settings.value('preferences/proxyPort', 0)

                return ProxyInfo(server_url = server, port = port, authn_required = authN, user = user, pwd = pwd)
        else:
            return None

    def __eq__(self, other):
        if other is None or not isinstance(other, ProxyInfo):
            return False

        ret = self.server_url == other.server_url \
              and self.port == other.port \
              and self.authn_required == other.authn_required
        if ret and self.authn_required:
            ret = self.user and self.pwd
        return ret

    def __ne__(self, other):
        return not self.__eq__(other)

class NoSIICARedirectHandler(HTTPRedirectHandler):
    MAX_TRIES = 3
    def __init__(self):
        self.tries = 0

    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        if code == 302 and self.tries < NoSIICARedirectHandler.MAX_TRIES:
            # normally should filter for redirects to SIICA token server
            # but that URL may change therefore it is not hard-coded here
            self.tries += 1
            return req
        else:
            return None

class BaseAutomationClient(object):
    """Client for the Nuxeo Content Automation HTTP API

    timeout is a short timeout to avoid having calls to fast JSON operations
    to block and freeze the application in case of network issues.

    blob_timeout is long (or infinite) timeout dedicated to long HTTP
    requests involving a blob transfer.

    """

    # Used for testing network errors
    _error = None

    application_name = Constants.APP_NAME
    _enable_trace = False
    _proxy = None
    _proxy_error_count = 0
    MAX_PROXY_ERROR_COUNT = 2

    @classproperty
    @classmethod
    def proxy(cls):
        if cls._proxy is None:
            cls._proxy = ProxyInfo.get_proxy()
        return cls._proxy

    @proxy.setter
    @classmethod
    def proxy(cls, val):
        cls._proxy = val

    @classmethod
    def get_proxy(cls):
        if cls._proxy is None:
            cls._proxy = ProxyInfo.get_proxy()
        return cls._proxy

    @classmethod
    def set_proxy(cls, val = None):
        cls._proxy = val

    @classproperty
    @classmethod
    def proxy_error_count(cls):
        cls._proxy_error_count += 1
        return cls._proxy_error_count

    @proxy_error_count.setter
    @classmethod
    def proxy_error_count(cls, val):
        cls._proxy_error_count = val

    permission = 'ReadWrite'
    cookiejar = CookieJar()

    def __init__(self, server_url, user_id, device_id,
                 password = None, token = None, repository = "default",
                 ignored_prefixes = None, ignored_suffixes = None,
                 timeout = 60, blob_timeout = None, 
                 skip_fetch_api=False):
        self.timeout = timeout
        self.blob_timeout = blob_timeout
        if ignored_prefixes is not None:
            self.ignored_prefixes = ignored_prefixes
        else:
            self.ignored_prefixes = DEFAULT_IGNORED_PREFIXES

        if ignored_suffixes is not None:
            self.ignored_suffixes = ignored_suffixes
        else:
            self.ignored_suffixes = DEFAULT_IGNORED_SUFFIXES

        if not server_url.endswith('/'):
            server_url += '/'
        self.server_url = server_url

        BaseAutomationClient.proxy_error_count = 0
        # TODO: actually use the repository info in the requests
        self.repository = repository

        self.user_id = user_id
        self.device_id = device_id
        self._update_auth(password = password, token = token)

        handlers = []
        proxy_support = None
        cookie_processor = urllib2.HTTPCookieProcessor(BaseAutomationClient.cookiejar)

        # NOTE 'proxy' classproperty does not work here (sample works!)
        # replace 'proxy' with 'get_proxy' and 'set_proxy' class methods
        if BaseAutomationClient.get_proxy() is None:
            # direct connection - disable proxy autodetect
            proxy_support = urllib2.ProxyHandler({})
        elif BaseAutomationClient.get_proxy().autodetect:
                # Autodetect uses the default ProxyServer.
                # The default is to read the list of proxies from the environment variables <protocol>_proxy.
                # If no proxy environment variables are set, in a Windows environment, proxy settings are obtained
                # from the registry Internet Settings section and in a Mac OS X environment, proxy information
                # is retrieved from the OS X System Configuration Framework.
                proxy_support = urllib2.ProxyHandler()
        else:
            proxy_url = r'%s:%d' % (BaseAutomationClient.get_proxy().server_url,
                                    BaseAutomationClient.get_proxy().port)
            proxy_support = urllib2.ProxyHandler({'http' : r'http://' + proxy_url,
                                                  'https' : r'https://' + proxy_url})
            if BaseAutomationClient.get_proxy().authn_required:
                proxy_url = r'%s:%s@%s:%d' % (BaseAutomationClient.get_proxy().user,
                                              BaseAutomationClient.get_proxy().pwd,
                                              BaseAutomationClient.get_proxy().server_url,
                                              BaseAutomationClient.get_proxy().port)
                proxy_support = urllib2.ProxyHandler({'http' : r'http://' + proxy_url,
                                                      'https' : r'https://' + proxy_url})
                pwd_mgr = HTTPPasswordMgr()

                pwd_mgr.add_password('sla', r'http://' + proxy_url,
                                    BaseAutomationClient.get_proxy().user,
                                    BaseAutomationClient.get_proxy().pwd)
                pwd_mgr.add_password('sla', r'https://' + proxy_url,
                                    BaseAutomationClient.get_proxy().user,
                                    BaseAutomationClient.get_proxy().pwd)
                proxy_auth = ProxyBasicAuthHandler(pwd_mgr)
                handlers.append(proxy_auth)

        handlers.append(proxy_support)
        handlers.append(cookie_processor)
        # DEBUG force raw HTTP debugging
        # NOTE this does not work in the installed version!!!
#        handlers.append(HTTPHandler(debuglevel=1))
#        handlers.append(HTTPSHandler(debuglevel=1))
        self.opener = urllib2.build_opener(*handlers)
        if not skip_fetch_api:
            self.automation_url = server_url + 'site/automation/'
            self.fetch_api()

    def log_request(self, req):
        if BaseAutomationClient._enable_trace:
            log.debug('------request-------')
            log.debug('request url: %s', req.get_full_url())
            log.debug('request host: %s', req.get_host())
            log.debug('original request host: %s', req.get_origin_req_host())
            log.debug('request type: %s', req.get_type())
            if req.has_data():
                log.debug('request data: %s...', str(req.get_data())[0:200])

    def log_response(self, rsp, data):
        if BaseAutomationClient._enable_trace:
            log.debug('------response------')
            log.debug('response code: %d', rsp.code)
            log.debug('--response headers--')
            for key, value in rsp.info().items():
                log.debug('%s: %s', key, value)
            log.debug('----response data---')
            # show data for text like data
            if not rsp.info().getencoding() == '7bit':
                data = 'binary data'
            log.debug('data: %s...', data[:500])

    def make_raise(self, error):
        """Make next calls to server raise the provided exception"""
        self._error = error

    def fetch_api(self):
        headers = self._get_common_headers()
        base_error_message = (
            _("Failed to connect to %s Content Automation on server %r"
            " with user %r")
        ) % (Constants.PRODUCT_NAME, self.server_url, self.user_id)
        try:
            req = urllib2.Request(self.automation_url, headers = headers)
            response = json.loads(self.opener.open(
                req, timeout = self.timeout).read())
            req = urllib2.Request(self.automation_url, headers = headers)
            BaseAutomationClient.cookiejar.add_cookie_header(req)
            # --- BEGIN DEBUG ----
            self.log_request(req)
            # --- END DEBUG ----
            raw_response = self.opener.open(req)
            data = raw_response.read()
            response = json.loads(data)
            # --- BEGIN DEBUG ----
            self.log_response(raw_response, data)
            # --- END DEBUG ----
        except urllib2.HTTPError as e:
            if e.code == 401 or e.code == 403:
                raise Unauthorized(self.server_url, self.user_id, e.code)
            elif e.code == 503:
                retry_after, schedules = self._check_maintenance_mode(e)
                if retry_after > 0:
                    raise MaintenanceMode(self.server_url, self.user_id, retry_after, schedules)
                else:
                    raise
            else:
                self._log_details(e)
                e.msg = base_error_message + _(": HTTP error %d") % e.code
                raise
        except Exception as e:
            self._log_details(e)
            if hasattr(e, 'msg'):
                e.msg = base_error_message + ": " + e.msg
            raise

        self.operations = {}
        for operation in response["operations"]:
            self.operations[operation['id']] = operation

    def execute(self, command, input = None, timeout = -1, **params):
        if self._error is not None:
            # Simulate a configurable (e.g. network or server) error for the
            # tests
            raise self._error

        self._check_params(command, input, params)
        headers = {
            "Content-Type": "application/json+nxrequest",
            "X-NXDocumentProperties": "*",
        }
        headers.update(self._get_common_headers())
        json_struct = {'params': {}}
        for k, v in params.items():
            if v is None:
                continue
            if k == 'properties':
                s = ""
                for propname, propvalue in v.items():
                    s += "%s=%s\n" % (propname, propvalue)
                json_struct['params'][k] = s.strip()
            else:
                json_struct['params'][k] = v

        if input:
            json_struct['input'] = input

        data = json.dumps(json_struct)

        url = self.automation_url + command
        log.trace("Calling '%s' with json payload: %r", url, data)
        base_error_message = (
            _("Failed to connect to %s Content Automation on server %r"
            " with user %r")
        ) % (Constants.PRODUCT_NAME, self.server_url, self.user_id)

        req = urllib2.Request(url, data, headers)
        timeout = self.timeout if timeout == -1 else timeout
        BaseAutomationClient.cookiejar.add_cookie_header(req)
        # --- BEGIN DEBUG ----
        self.log_request(req)
        # ---- END DEBUG -----
        try:
            resp = self.opener.open(req, timeout = timeout)
            # --- BEGIN DEBUG ----
            if DEBUG_MAINTENANCE_EXCEPTION:
                from StringIO import StringIO
                msg = '{"Status": "maintenance", "ScheduleItems": [\
                        {"CreationDate": "2013-02-15T09:50:22.001",\
                         "Target": "qadm.sharpb2bcloud.com",\
                         "Service": "Cloud Portal Service",\
                         "FromDate": "2013-02-16T23:00:00Z",\
                         "ToDate": "2013-02-17T03:00:00Z"\
                        }]\
                        }'
                fp = StringIO(msg)
                raise urllib2.HTTPError(url, 503, "service unavailable", None, fp)
            # ---- END DEBUG -----
        except urllib2.HTTPError as e:
            # NOTE cannot rewind the error stream from maintenance server!
#            self._log_details(e)
            if e.code == 401 or e.code == 403:
                raise Unauthorized(url, self.user_id, e.code, data)
            elif e.code == 404:
                # Token based auth is not supported by this server
                return None
            elif e.code == 503:
                retry_after, schedules = self._check_maintenance_mode(e)
                if retry_after > 0:
                    raise MaintenanceMode(self.server_url, self.user_id, retry_after, schedules)
                else:
                    raise

            else:
                e.msg = base_error_message + _(": HTTP error %d") % e.code
                raise e
        except urllib2.URLError, e:
            self._log_details(e)
            # NOTE the Proxy handler not always shown in the dictionary
#            if urllib2.getproxies().has_key('http'):
            if BaseAutomationClient.get_proxy() is not None and \
                BaseAutomationClient.proxy_error_count < BaseAutomationClient.MAX_PROXY_ERROR_COUNT:
                raise ProxyConnectionError(e)
            else:
                raise
        except Exception, e:
            self._log_details(e)
            raise

        info = resp.info()
        s = resp.read()
        # --- BEGIN DEBUG ----
        self.log_response(resp, s)
        # ---- END DEBUG -----
        content_type = info.get('content-type', '')
        if content_type.startswith("application/json"):
            log.trace("Response for '%s' with json payload: %r", url, s)
            return json.loads(s) if s else None
        else:
            log.trace("Response for '%s' with content-type: %r", url,
                      content_type)
            return s

    def execute_with_blob(self, command, blob_content, filename, **params):
        self._check_params(command, None, params)

        container = MIMEMultipart("related",
                type = "application/json+nxrequest",
                start = "request")

        d = {'params': params}
        json_data = json.dumps(d)
        json_part = MIMEBase("application", "json+nxrequest")
        json_part.add_header("Content-ID", "request")
        json_part.set_payload(json_data)
        container.attach(json_part)

        ctype, encoding = mimetypes.guess_type(filename)
        if ctype:
            maintype, subtype = ctype.split('/', 1)
        else:
            maintype, subtype = "application", "octet-stream"
        blob_part = MIMEBase(maintype, subtype)
        blob_part.add_header("Content-ID", "input")
        blob_part.add_header("Content-Transfer-Encoding", "binary")

        # Quote UTF-8 filenames eventhough JAX-RS does not seem to be able
        # to retrieve them as per: https://tools.ietf.org/html/rfc5987
        quoted_filename = urllib.quote(filename.encode('utf-8'))
        content_disposition = ("attachment; filename*=UTF-8''%s"
                                % quoted_filename)
        blob_part.add_header("Content-Disposition", content_disposition)
        blob_part.set_payload(blob_content)
        container.attach(blob_part)

        # Create data by hand :(
        boundary = "====Part=%s=%s===" % (str(time.time()).replace('.', '='),
                                          random.randint(0, 1000000000))
        headers = {
            "Accept": "application/json+nxentity, */*",
            "Content-Type": ('multipart/related;boundary="%s";'
                             'type="application/json+nxrequest";'
                             'start="request"')
            % boundary,
        }
        headers.update(self._get_common_headers())

        # TODO: find a way to stream the parts without loading them all in
        # memory as a byte string

        # The code http://atlee.ca/software/poster/ might provide some
        # guidance to implement this although it cannot be reused directly
        # as we need tighter control on the headers of the multipart
        data = (
            "--%s\r\n"
            "%s\r\n"
            "--%s\r\n"
            "%s\r\n"
            "--%s--"
        ) % (
            boundary,
            json_part.as_string(),
            boundary,
            blob_part.as_string(),
            boundary,
        )
        url = self.automation_url.encode('ascii') + command
        base_error_message = (
            "Failed to connect to %s Content Automation on server %r"
            " with user %r"
        ) % (Constants.PRODUCT_NAME, self.server_url, self.user_id)
        log.trace("Calling '%s' for file '%s'", url, filename)
        req = urllib2.Request(url, data, headers)
        BaseAutomationClient.cookiejar.add_cookie_header(req)
        # --- BEGIN DEBUG ----
        self.log_request(req)
        # ---- END DEBUG -----
        try:
            resp = self.opener.open(req, timeout = self.blob_timeout)
            # --- BEGIN DEBUG ----
            if DEBUG_QUOTA_EXCEPTION:
                from StringIO import StringIO
                msg = '{ "entity-type": "exception",\
                        "type":"com.sharplabs.clouddesk.operations.StorageExceededException",\
                        "status": "500",\
                        "message": "Failed to execute operation: StorageUsed.Get",\
                        "stack": ""\
                    }'
                fp = StringIO(msg)
                raise urllib2.HTTPError(url, 500, "internal server error", None, fp)
            # ---- END DEBUG -----
        except urllib2.HTTPError as e:
            self._log_details(e)
            if e.code == 401 or e.code == 403:
                raise Unauthorized(self.server_url, self.user_id, e.code)
            elif e.code == 404:
                # Token based auth is not supported by this server
                return None
            elif e.code == 500:
                if self.check_quota_exceeded_error(e):
                    ref = params['document']
                    raise QuotaExceeded(self.server_url, self.user_id, ref, len(blob_content))
                else:
                    raise
            elif e.code == 503:
                retry_after, schedules = self._check_maintenance_mode(e)
                if retry_after > 0:
                    raise MaintenanceMode(self.server_url, self.user_id, retry_after, schedules)
                else:
                    raise

            else:
                e.msg = base_error_message + ": HTTP error %d" % e.code
                raise e
        except urllib2.URLError, e:
            self._log_details(e)
            if BaseAutomationClient.get_proxy() is not None and \
                BaseAutomationClient.proxy_error_count < BaseAutomationClient.MAX_PROXY_ERROR_COUNT:
                raise ProxyConnectionError(e)
            else:
                raise
        except Exception as e:
            self._log_details(e)
            raise

        info = resp.info()
        s = resp.read()
        # --- BEGIN DEBUG ----
        self.log_response(resp, s)
        # ---- END DEBUG -----
        content_type = info.get('content-type', '')
        if content_type.startswith("application/json"):
            log.trace("Response for '%s' with json payload: %r", url, s)
            return json.loads(s) if s else None
        else:
            log.trace("Response for '%s' with content-type: %r", url,
                      content_type)
            return s

    def is_addon_installed(self):
        return 'NuxeoDrive.GetRoots' in self.operations

    def request_token(self, revoke = False):
        """Request and return a new token for the user"""

        parameters = {
            'deviceId': self.device_id,
            'applicationName': self.application_name,
            'computerName': platform.node(),
            'permission': self.permission,
            'revoke': 'true' if revoke else 'false',
        }
        device_description = DEVICE_DESCRIPTIONS.get(sys.platform)
        if device_description:
            parameters['deviceDescription'] = device_description

        # new CloudDesk service to register token with computer name
        url = self.server_url + 'authentication/cloudtoken?'
        url += urlencode(parameters)

        headers = self._get_common_headers()
        base_error_message = (
            _("Failed to connect to %s Content Automation on server %r"
            " with user %r")
        ) % (Constants.PRODUCT_NAME, self.server_url, self.user_id)
        if not revoke:
            prev_opener = self.opener
            # add a custom redirect handler for requests which are redirected to the SIICA login server
            # this is a known issue for CloudDessk
            # TODO do I need to change the order of handlers and how?
            self._add_redirect_handler()
        else:
            prev_opener = None
        try:
            log.trace("Calling '%s' with headers: %r", url, headers)
            req = urllib2.Request(url, headers = headers)
            BaseAutomationClient.cookiejar.add_cookie_header(req)
            token = self.opener.open(req, timeout = self.timeout).read()
            token2 = token.decode('ascii')
            log.debug("received token: %s", token)
        except urllib2.HTTPError as e:
            self._log_details(e)
            if e.code == 401 or e.code == 403:
                raise Unauthorized(url, self.user_id, e.code)
            elif e.code == 404:
                # Token based auth is not supported by this server
                return None
            else:
                e.msg = base_error_message + _(": HTTP error %d") % e.code
                raise e
        except urllib2.URLError, e:
            self._log_details(e)
            if BaseAutomationClient.get_proxy() is not None and \
                BaseAutomationClient.proxy_error_count < BaseAutomationClient.MAX_PROXY_ERROR_COUNT:
                raise ProxyConnectionError(e)
            else:
                raise
        except UnicodeDecodeError:
            log.debug('token contains non-ascii characters')
            # NOTE this is a workaround the issue of CloudDesk redirecting to
            # the login page: intermittently, and when providing invalid credentials
            return None
        except Exception as e:
            self._log_details(e)
            if hasattr(e, 'msg'):
                e.msg = base_error_message + ": " + e.msg
            raise
        finally:
            # reset the opener
            if prev_opener is not None:
                self.opener = prev_opener

        # Use the (potentially re-newed) token from now on
        if not revoke:
            self._update_auth(token = token)
        return token

    def revoke_token(self):
        self.request_token(revoke = True)

    def wait(self):
        self.execute("NuxeoDrive.WaitForAsyncCompletion")

    def update_last_access(self, token):
        if token is not None:
            # server is using token, not password for authentication
            try:
                self.execute('Drive.LastAccess', lastAccess = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                             token = token)
            except ValueError:
                log.debug("operation 'Drive.LastAccess' is not implemented.")

    def _update_auth(self, password = None, token = None):
        """Select the most appropriate authentication heads based on credentials"""
        if token is not None:
            self.auth = ('X-Authentication-Token', token)
        elif password is not None:
            basic_auth = 'Basic %s' % base64.b64encode(
                    self.user_id + ":" + password).strip()
            self.auth = ("Authorization", basic_auth)
        else:
            raise ValueError(_("Either password or token must be provided"))

    def _get_common_headers(self):
        """Headers to include in every HTTP requests

        Includes the authentication heads (token based or basic auth if no
        token).

        Also include an application name header to make it possible for the
        server to compute access statistics for various client types (e.g.
        browser vs devices).

        """
        return {
            'X-Application-Name': self.application_name,
            self.auth[0]: self.auth[1],
        }

    def _check_params(self, command, input, params):
        if command not in self.operations:
            raise ValueError(_("'%s' is not a registered operations.") % command)
        method = self.operations[command]
        required_params = []
        other_params = []
        for param in method['params']:
            if param['required']:
                required_params.append(param['name'])
            else:
                other_params.append(param['name'])

        for param in params.keys():
            if (not param in required_params
                and not param in other_params):
                raise ValueError(_("Unexpected param '%s' for operation '%s")
                                 % (param, command))
        for param in required_params:
            if not param in params:
                raise ValueError(
                    _("Missing required param '%s' for operation '%s'") % (
                        param, command))

        # TODO: add typechecking

    def _log_details(self, e):
        if hasattr(e, "fp"):
            detail = e.fp.read()
            try:
                exc = json.loads(detail)
                log.debug(exc['message'])
                log.debug(exc['stack'], exc_info = True)
            except:
                # Error message should always be a JSON message,
                # but sometimes it's not
                log.debug(detail)
            # reset the file at the beginning if it needs to be read again
            if hasattr(e.fp, "seek"):
                e.fp.seek(0, 0)

    def check_quota_exceeded_error(self, e):
        if hasattr(e, "fp"):
                detail = e.fp.read()
                try:
                    exc = json.loads(detail)
                    if exc['type'].endswith('StorageExceededException'):
                        return True
                except:
                    pass
        return False

    def _check_maintenance_mode(self, e):
        retry_after = 0
        schedules = None
        # get retry-after header
        #------BEGIN DEBUG------
#        s_retry_after = e.headers['retry-after']
        s_retry_after = '10'
        try:
            retry_after = int(s_retry_after)
        except ValueError:
            pass
        #-------END DEBUG-------

        if hasattr(e, "fp"):
            detail = e.fp.read()
            try:
                schedules = json.loads(detail)
            except:
                pass

        return retry_after, schedules

    def _get_maintenance_schedule(self, server_binding):
        netloc = urlparse.urlsplit(server_binding.server_url).netloc
        req = urllib2.Request(urlparse.urljoin(Constants.MAINTENANCE_SERVICE_URL, netloc))
        # --- BEGIN DEBUG ----
        self.log_request(req)
        # ---- END DEBUG -----

        try:
            resp = self.opener.open(req)
            # extract the json payload as it is wrapped insode a <string><.string>!
            data = resp.read()
            # --- BEGIN DEBUG ----
            self.log_response(resp, data)
            # ---- END DEBUG -----
            # NOTE Workaround this response which is supposed to be JSON but it looks like this
            # <?xml version="1.0" encoding="utf-8"?><string>...json data...</string>
            # and the Content-Type is 'application/xml'
            data = data.partition('<string>')[2]
            data = data.rpartition('</string')[0]
            return json.loads(data)
        except Exception, e:
            log.debug('error retrieving schedule: %s', str(e))
            return None

    def _get_upgrade_info(self, server_binding):
        from nxdrive._version import __version__

        url = Constants.UPGRADE_SERVICE_URL + Constants.SHORT_APP_NAME + '/' + __version__ + '/' + sys.platform
        req = urllib2.Request(url)
        # --- BEGIN DEBUG ----
        self.log_request(req)
        # ---- END DEBUG -----

        try:
            resp = self.opener.open(req)
            # extract the json payload as it is wrapped insode a <string><.string>!
            data = resp.read()
            # --- BEGIN DEBUG ----
            self.log_response(resp, data)
            # ---- END DEBUG -----
            # NOTE Workaround this response which is supposed to be JSON but it looks like this
            # <?xml version="1.0" encoding="utf-8"?><string>...json data...</string>
            # and the Content-Type is 'application/xml'
            data = data.partition('<string>')[2]
            data = data.rpartition('</string')[0]
            info = json.loads(data)
            assert(info['AppName'].lower() == Constants.SHORT_APP_NAME.lower())
            return info['CreationDate'], info['Version'], info['DownloadUrl']
        except Exception, e:
            log.debug('error retrieving upgrade version: %s', str(e))
            return None, None, None
        
    def _add_redirect_handler(self):
        my_redirect_handler = NoSIICARedirectHandler()
        my_redirect_handler.add_parent(self.opener)
        for i in xrange(len(self.opener.handlers)):
            if isinstance(self.opener.handlers[i], HTTPRedirectHandler):
                # put in front of the default redirect handler
                my_redirect_handler.handler_order = self.opener.handlers[i].handler_order - 10
                break
        self.opener.add_handler(my_redirect_handler)
