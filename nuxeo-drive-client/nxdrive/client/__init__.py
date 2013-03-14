from nxdrive.client.common import NotFound
from nxdrive.client.base_automation_client import Unauthorized
from nxdrive.client.base_automation_client import QuotaExceeded
from nxdrive.client.base_automation_client import MaintenanceMode
from nxdrive.client.remote_document_client import NuxeoDocumentInfo
from nxdrive.client.local_client import DEDUPED_BASENAME_PATTERN
from nxdrive.client.local_client import safe_filename
from nxdrive.client.local_client import LocalClient
from nxdrive.client.remote_document_client import FolderInfo
from nxdrive.client.base_automation_client import BaseAutomationClient
from nxdrive.client.remote_document_client import RemoteDocumentClient
from nxdrive.client.remote_file_system_client import RemoteFileSystemClient
from nxdrive.client.remote_service_client import RemoteMaintServiceClient
from nxdrive.client.remote_service_client import RemoteUpgradeServiceClient
from nxdrive.client.base_automation_client import ProxyInfo

# Backward compatibility with old remote client name, to be removed
NuxeoClient = RemoteDocumentClient
