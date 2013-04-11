@echo off
echo Building 32bit CpoIconSynced
cd /d %~dp0
devenv.exe CpoIconOverlaySynced.sln /project "CpoIconOverlaySynced.vcxproj" /Rebuild "Release|win32"
echo Building 64bit CpoIconSynced
devenv.exe CpoIconOverlaySynced.sln /project "CpoIconOverlaySynced.vcxproj" /Rebuild "Release|x64"
cd ..
