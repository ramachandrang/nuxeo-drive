@echo off
echo #########################################
echo ### Cpo Icon Overlay DLL Build Script ###
echo #########################################
cd /d %~dp0
Call setEnv.bat
Call .\CpoIconOverlaySynced\build.bat
Call .\CpoIconOverlayInProgress\build.bat
Call .\CpoIconOverlayConflict\build.bat
cd ..
::reset cmd prompt color from devenv building
Color