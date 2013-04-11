@echo off
cd /d %~dp0
echo Building 32bit CpoIconOverlayConflicted
devenv.exe "CpoIconOverlayConflicted.sln" /project "CpoIconOverlayConflicted.vcxproj" /Rebuild "Release|win32"
echo Building 64bit CpoIconOverlayConflicted
devenv.exe "CpoIconOverlayConflicted.sln" /project "CpoIconOverlayConflicted.vcxproj" /Rebuild "Release|x64"
cd ..