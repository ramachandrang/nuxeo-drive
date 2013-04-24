@echo off
set GITREPO=c:\gitrepo\nuxeo-drive
set BUILD_DIR=c:\temp\cpo\build
set PROGRAM_FILES=C:\Program Files (x86)
set INSTALL_DIR=Cloud Portal Office Desktop
set SETUP_SCRIPT=CPODesktop-setup-script.iss
set SETUP_SCRIPT2=InfoAfterInstall.txt
set INNO_COMPILER=c:\Program Files (x86)\Inno Setup 5\iscc
set DLL_DIR=CpoIconOverlay
set DLL_BUILD_SCRIPT=build-dlls.bat
set CPO_EXE=CpoDesktop.exe
set VERSION=0.2.3

pushd

echo delete previous build...
del /S /Q /F "%BUILD_DIR%\*"
rmdir /S /Q "%BUILD_DIR%"
del /S /Q /F "%PROGRAM_FILES%\%INSTALL_DIR%\*"
rmdir /S /Q "%PROGRAM_FILES%\%INSTALL_DIR%"

cd %GITREPO%
echo building the installation directory structure...
python setup.py install --freeze build_exe

echo copy to build dir...
xcopy /R /Y /S /I "%PROGRAM_FILES%\%INSTALL_DIR%" "%BUILD_DIR%\%INSTALL_DIR%"

echo copy batch files...
xcopy /R /Y /S /I BatchFiles "%BUILD_DIR%\BatchFiles"

echo copy redist packages...
echo f | xcopy cpo_x86Setup.exe /S /Y %BUILD_DIR%\RedistPackages\32bit\
echo f | xcopy cpo_x64Setup.exe /S /Y %BUILD_DIR%\RedistPackages\64bit\

echo build DLLs...
call "%DLL_DIR%\%DLL_BUILD_SCRIPT%"

echo copy DLLs...
# this source location is no longer used since DLLs are being built
# xcopy /R /Y /S /I "%GITREPO%\nuxeo-drive-client\nxdrive\data\bin" "%BUILD_DIR%\Dll"
xcopy /R /Y /S /I "%DLL_DIR%\bin\Win32\*.dll" "%BUILD_DIR%\Dll\32bit"
xcopy /R /Y /S /I "%DLL_DIR%\bin\x64\*.dll" "%BUILD_DIR%\Dll\64bit"

xcopy /R /Y /S /I "%GITREPO%\PreReqDll" "%BUILD_DIR%\PreReqDll"

echo copy setup script...
copy /Y %SETUP_SCRIPT% %BUILD_DIR%
copy /Y %SETUP_SCRIPT2% %BUILD_DIR%

echo build the setup exe...
rem "%BUILD_DIR%\%INSTALL_DIR%\%CPO_EXE%" -v > version.txt
rem set /p VERSION=<version.txt
"%INNO_COMPILER%" /fCPODesktop-%VERSION%-Win32-setup /O"%BUILD_DIR%\dist" "%BUILD_DIR%\%SETUP_SCRIPT%"

popd
