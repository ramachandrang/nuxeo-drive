@echo off
cd /d %~dp0
echo Building 32bit CpoIconSynced
devenv.exe CpoIconOverlaySynced.sln /project "CpoIconOverlaySynced.vcxproj" /Rebuild "Release|win32"
echo Building 64bit CpoIconSynced
devenv.exe CpoIconOverlaySynced.sln /project "CpoIconOverlaySynced.vcxproj" /Rebuild "Release|x64"
del /q .\Release\*.*
del /q .\x64\Release\*.*
cd ..
