@echo off
cd /d %~dp0
echo Building 32bit CpoIconOverlayInProgress
devenv.exe "CpoIconOverlayInProgress.sln" /project "CpoIconOverlayInProgress.vcxproj" /Rebuild "Release|win32"
echo Building 64bit CpoIconOverlayInProgress
devenv.exe "CpoIconOverlayInProgress.sln" /project "CpoIconOverlayInProgress.vcxproj" /Rebuild "Release|x64"
del /q .\Release\*.*
del /q .\x64\Release\*.*
cd ..
