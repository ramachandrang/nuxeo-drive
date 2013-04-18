# Powershell script: save on Desktop and Right Click "Run with PowerShell"

# Get ready to download and install dev tools from the web
$storagedir = "$pwd\nxdrive-downloads"
mkdir $storagedir -ErrorAction SilentlyContinue
$webclient = New-Object System.Net.WebClient


# Install cx_Freeze manually as pip does not work for this package
$url = "http://downloads.sourceforge.net/project/cx-freeze/4.3/cx_Freeze-4.3.win32-py2.7.msi?r=http%3A%2F%2Fcx-freeze.sourceforge.net%2F&ts=1342189378&use_mirror=dfn"
$cx_freeze = "$storagedir\cx_Freeze-4.3.win32-py2.7.msi"
echo "Downloading cx_Freeze from $url"
$webclient.DownloadFile($url, $cx_freeze)
echo "Installing cx_Freeze from $cx_freeze"
msiexec.exe /qn /I $cx_freeze

echo "You can now clone the nuxeo-drive repo:"
echo "git clone https://github.com/nuxeo/nuxeo-drive.git"
echo ""
echo "Then install the developer dependencies:"
echo "pip install -r nuxeo-drive/nuxeo-drive-client/dev-requirements.txt"
