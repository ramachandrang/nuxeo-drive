"""Common Nuxeo Automation client utilities."""

import sys
import platform
import base64
import json
import urllib2
import urlparse
import mimetypes
import random
import time
import string
from datetime import datetime
from urllib import urlencode
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
        return ("'%s' is not authorized to access '%s' with"
                " the provided credentials. http code=%d, data=%s" % (self.user_id, self.url, self.code, str(self.data)))

class QuotaExceeded(Exception):
    def __init__(self, url, user_id, ref, size):
        self.url = url
        self.user_id = user_id
        self.ref = ref
        self.size = size

    def __str__(self):
        return ("'%s' exceeded quota for '%s' when"
                " storing document %s" % (self.user_id, self.url, self.ref))

class MaintenanceMode(Exception):
    def __init__(self, url, user_id, retry_after, schedules):
        self.url = url
        self.user_id = user_id
        self.retry_after = retry_after
        self.msg = '%s is in maintenance mode' % Constants.PRODUCT_NAME
        if schedules is not None:
            status = schedules['Status']
            if len(schedules['ScheduleItems']) == 1:
                schedule = schedules['ScheduleItems'][0]
            else:
                schedule = None
            self.msg = get_maintenance_message(status, schedule=schedule)

    def __str__(self):
        return self.msg

class ProxyInfo(object):
    """Holder class for proxy information"""

    PORT = '8090'
    PORT_INTEGER = int(PORT)
    TYPES = ['HTTP', 'SOCKS4', 'SOCKS5']
    PROXY_SERVER = 'server'
    PROXY_AUTODETECT = 'autodetect'
    PROXY_DIRECT = 'direct'

    def __init__(self, type = 'HTTP', server_url = None, port = None, authn_required = False, user = None, pwd = None):
        self.type = type
        if type != ProxyInfo.TYPES[0]:
            raise ProxyConfigurationError('protocol type not supported')
        self.autodetect = False
        if not server_url:
            self.autodetect = True
        self.authn_required = authn_required
        if not user and authn_required:
            raise ProxyConfigurationError('missing username')
        self.server_url = server_url
        self.port = port
        if server_url is None or port is None:
            raise ProxyConfigurationError('missing server or port')
        self.user = user
        self.pwd = pwd

    @staticmethod
    def get_proxy():
        settings = create_settings()
        if settings is None:
            return None

        useProxy = settings.value('preferences/useProxy', ProxyInfo.PROXY_DIRECT)
        if useProxy == ProxyInfo.PROXY_DIRECT:
            return None

        proxyType = settings.value('preferences/proxyType', 'HTTP')
        server = settings.value('preferences/proxyServer')
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

        return ProxyInfo(proxyType, server, port, authN, user, pwd)

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


class BaseAutomationClient(object):
    """Client for the Nuxeo Content Automation HTTP API"""

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
                 password=None, token=None, repository="default",
                 ignored_prefixes=None, ignored_suffixes=None,
                 timeout=20):
        self.timeout = timeout
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
        cookie_processor = urllib2.HTTPCookieProcessor(BaseAutomationClient.cookiejar)

        if BaseAutomationClient.proxy is not None:
            if not BaseAutomationClient.proxy.autodetect and BaseAutomationClient.proxy.type == 'HTTP':
                proxy_url = '%s:%d' % (BaseAutomationClient.proxy.server_url, BaseAutomationClient.proxy.port)
                proxy_support = urllib2.ProxyHandler({'http' : proxy_url, 'https' : proxy_url})
                self.opener = urllib2.build_opener(cookie_processor, proxy_support)
            else:
                # Autodetect uses the default ProxyServer
                # Autodetect is not implemented
                self.opener = urllib2.build_opener(cookie_processor)
        else:
            # direct connection - disable autodetect
            proxy_support = urllib2.ProxyHandler({})
            self.opener = urllib2.build_opener(cookie_processor, proxy_support)

        BaseAutomationClient._enable_trace = False
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

    def log_response(self, rsp):
        if BaseAutomationClient._enable_trace:
            log.debug('------response------')
            log.debug('response code: %d', rsp.code)
            log.debug('--response headers--')
            for key, value in rsp.info().items():
                log.debug('%s: %s', key, value)
            log.debug('----response data---')
            log.debug('data: %s...', str(rsp)[0:200])

    def make_raise(self, error):
        """Make next calls to server raise the provided exception"""
        self._error = error

    def fetch_api(self):
        headers = self._get_common_headers()
        base_error_message = (
            "Failed not connect to %s Content Automation on server %r"
            " with user %r"
        ) % (Constants.PRODUCT_NAME, self.server_url, self.user_id)
        try:
            req = urllib2.Request(self.automation_url, headers=headers)
            response = json.loads(self.opener.open(
                req, timeout=self.timeout).read())
            req = urllib2.Request(self.automation_url, headers = headers)
            BaseAutomationClient.cookiejar.add_cookie_header(req)
            # --- BEGIN DEBUG ----
            self.log_request(req)
            # --- END DEBUG ----
            raw_response = self.opener.open(req)
            response = json.loads(raw_response.read())
            # --- BEGIN DEBUG ----
            self.log_response(raw_response)
            # --- END DEBUG ----
        except urllib2.HTTPError as e:
            if e.code == 401 or e.code == 403:
                raise Unauthorized(self.server_url, self.user_id, e.code)
            else:
                self._log_details(e)
                e.msg = base_error_message + ": HTTP error %d" % e.code
                raise e
        except Exception as e:
            self._log_details(e)
            if hasattr(e, 'msg'):
                e.msg = base_error_message + ": " + e.msg
            raise

        self.operations = {}
        for operation in response["operations"]:
            self.operations[operation['id']] = operation

    def execute(self, command, input = None, **params):
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
            "Failed not connect to %s Content Automation on server %r"
            " with user %r"
        ) % (Constants.PRODUCT_NAME, self.server_url, self.user_id)

        req = urllib2.Request(url, data, headers)
        BaseAutomationClient.cookiejar.add_cookie_header(req)
        # --- BEGIN DEBUG ----
        self.log_request(req)
        # ---- END DEBUG -----
        try:
            resp = self.opener.open(req, timeout=self.timeout)
            # --- BEGIN DEBUG ----
#            from StringIO import StringIO
#            msg = '{"Status": "maintenance", "ScheduleItems": [\
#                    {"CreationDate": "2013-02-15T09:50:22.001",\
#                     "Target": "qadm.sharpb2bcloud.com",\
#                     "Service": "Cloud Portal Service",\
#                     "FromDate": "2013-02-16T23:00:00Z",\
#                     "ToDate": "2013-02-17T03:00:00Z"\
#                    }]\
#                    }'
#            fp = StringIO(msg)
#            raise urllib2.HTTPError(url, 503, "service unavailable", None, fp)
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
                e.msg = base_error_message + ": HTTP error %d" % e.code
                raise e
        except urllib2.URLError, e:
            self._log_details(e)
            # NOTE the Proxy handler not always shown in the dictionary
#            if urllib2.getproxies().has_key('http'):
            if BaseAutomationClient.proxy is not None and \
                BaseAutomationClient.proxy_error_count < BaseAutomationClient.MAX_PROXY_ERROR_COUNT:
                raise ProxyConnectionError(e)
            else:
                raise
        except Exception, e:
            self._log_details(e)
            raise

        # --- BEGIN DEBUG ----
        self.log_response(resp)
        # ---- END DEBUG -----
        info = resp.info()
        s = resp.read()

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
            maintype, subtype = "application", "binary"
        blob_part = MIMEBase(maintype, subtype)
        blob_part.add_header("Content-ID", "input")
        blob_part.add_header("Content-Transfer-Encoding", "binary")
        ascii_filename = filename.encode('ascii', 'ignore')
        # content_disposition = "attachment; filename=" + ascii_filename
        # quoted_filename = urllib.quote(filename.encode('utf-8'))
        # content_disposition += "; filename filename*=UTF-8''" \
        #    + quoted_filename
        # print content_disposition
        # blob_part.add_header("Content-Disposition:", content_disposition)

        # XXX: Use ASCCI safe version of the filename for now
        blob_part.add_header('Content-Disposition', 'attachment',
                             filename = ascii_filename)

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
            # TODO: we should find a way to stream the content of the blob
            # to avoid loading it in memory
            blob_part.as_string(),
            boundary,
        )
        url = self.automation_url.encode('ascii') + command
        base_error_message = (
            "Failed not connect to %s Content Automation on server %r"
            " with user %r"
        ) % (Constants.PRODUCT_NAME, self.server_url, self.user_id)
        log.trace("Calling '%s' for file '%s'", url, filename)
        req = urllib2.Request(url, data, headers)
        BaseAutomationClient.cookiejar.add_cookie_header(req)
        # --- BEGIN DEBUG ----
        self.log_request(req)
        # ---- END DEBUG -----
        try:
            resp = self.opener.open(req, timeout=self.timeout)
            # --- BEGIN DEBUG ----
#            from StringIO import StringIO
#            msg = '{ "entity-type": "exception",\
#                    "type":"com.sharplabs.clouddesk.operations.StorageExceededException",\
#                    "status": "500",\
#                    "message": "Failed to execute operation: StorageUsed.Get",\
#                    "stack": ""\
#                }'
#            fp = StringIO(msg)
#            raise urllib2.HTTPError(url, 500, "internal server error", None, fp)
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
            if BaseAutomationClient.proxy is not None and \
                BaseAutomationClient.proxy_error_count < BaseAutomationClient.MAX_PROXY_ERROR_COUNT:
                raise ProxyConnectionError(e)
            else:
                raise
        except Exception as e:
            self._log_details(e)
            raise

        # --- BEGIN DEBUG ----
        self.log_response(resp)
        # ---- END DEBUG -----
        info = resp.info()
        s = resp.read()

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
            "Failed to connect to %s Content Automation on server %r"
            " with user %r"
        ) % (Constants.PRODUCT_NAME, self.server_url, self.user_id)
        try:
            log.trace("Calling '%s' with headers: %r", url, headers)
            req = urllib2.Request(url, headers=headers)
            BaseAutomationClient.cookiejar.add_cookie_header(req)
            token = self.opener.open(req, timeout=self.timeout).read()
            log.debug("received token: %s", token)
        except urllib2.HTTPError as e:
            self._log_details(e)
            if e.code == 401 or e.code == 403:
                raise Unauthorized(url, self.user_id, e.code)
            elif e.code == 404:
                # Token based auth is not supported by this server
                return None
            else:
                e.msg = base_error_message + ": HTTP error %d" % e.code
                raise e
        except urllib2.URLError, e:
            self._log_details(e)
            if BaseAutomationClient.proxy is not None and \
                BaseAutomationClient.proxy_error_count < BaseAutomationClient.MAX_PROXY_ERROR_COUNT:
                raise ProxyConnectionError(e)
            else:
                raise
        except Exception as e:
            self._log_details(e)
            if hasattr(e, 'msg'):
                e.msg = base_error_message + ": " + e.msg
            raise

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
                self.execute('Drive.LastAccess', lastAccess=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                             token=token)
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
            raise ValueError("Either password or token must be provided")

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
            raise ValueError("'%s' is not a registered operations." % command)
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
                raise ValueError("Unexpected param '%s' for operation '%s"
                                 % (param, command))
        for param in required_params:
            if not param in params:
                raise ValueError(
                    "Missing required param '%s' for operation '%s'" % (
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
            # --- BEGIN DEBUG ----
            self.log_response(resp)
            # ---- END DEBUG -----
            # extract the json payload as it is wrapped insode a <string><.string>!
            data = resp.read()
            # NOTE Workaround this response which is supposed to be JSON but it looks like this
            # <?xml version="1.0" encoding="utf-8"?><string>...json data...</string>
            # and the Content-Type is 'application/xml'
            data = data.partition('<string>')[2]
            data = data.rpartition('</string')[0]
            return json.loads(data)
        except Exception, e:
            log.debug('error retrieving schedule: %s', str(e))
            return None

    