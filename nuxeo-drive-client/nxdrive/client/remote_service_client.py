'''
Created on Mar 13, 2013

@author: constantinm

API to access external services, e.g. maintenance or software upgrade
'''
import urllib2
import json

from nxdrive.client.base_automation_client import BaseAutomationClient
from nxdrive.logging_config import get_logger
from nxdrive import Constants

log = get_logger(__name__)

class RemoteMaintServiceClient(BaseAutomationClient):
    """Web service client for the external maintenance service. Reuse the basic remote client configuration.
    """

    def get_maintenance_schedule(self, server_binding):
        req = urllib2.Request(self.server_url)
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

class RemoteUpgradeServiceClient(BaseAutomationClient):
    """Web service client for the external software upgrade service. Reuse the basic remote client configuration.
    """

    def get_upgrade_info(self, server_binding):
        req = urllib2.Request(self.server_url)
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
            if info is None:
                return None, None, None
            assert(info['AppName'].lower() == Constants.SHORT_APP_NAME.lower())
            return info['CreationDate'], info['Version'], info['DownloadUrl']
        except Exception, e:
            log.debug('error retrieving upgrade version: %s', str(e))
            return None, None, None
