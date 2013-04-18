echo off
set SRC=C:\gitrepo\nuxeo-drive
set REPO=C:\gitrepo\clouddesk-applications
set APP_DIR=CloudDesktopSync
set DST=%REPO%\%APP_DIR%

echo copying shell extension project...
xcopy /S /I /Y %SRC%\CpoIconOverlay %DST%\CpoIconOverlay

echo copying desktop sync project...
xcopy /S /I /Y /EXCLUDE:metadata %SRC%\nuxeo-drive-client %DST%\nuxeo-drive-client

echo copying tools...
xcopy /S /I /Y %SRC%\tools %DST%\tools
copy /Y "%SRC%\*.bat" "%DST%"
copy /Y "%SRC%\cpo_*" "%DST%"

echo copying misc files...
copy /Y %SRC%\setup.* %DST%
copy /Y %SRC%\README.* %DST%
copy /Y %SRC%\*.js %DST%
