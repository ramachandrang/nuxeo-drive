@echo off
if not "%VS_INSTALL_DIR%" == "" goto gotVSInstall
set VS_INSTALL_DIR=C:\Program Files (x86)\Microsoft Visual Studio 10.0
:gotVSInstall
::if exist "%VS_INSTALL_DIR%\SDK\v3.5\Bin\nmake.exe" goto okHome
if exist "%VS_INSTALL_DIR%\VC\bin\nmake.exe" goto okHome
echo The VS_INSTALL_DIR environment variable is not defined correctly
goto end

:okHome

set PATH=%VS_INSTALL_DIR%\VC\bin;%VS_INSTALL_DIR%\bin;%VS_INSTALL_DIR%\PlatformSDK\bin;%VS_INSTALL_DIR%\PlatformSDK\Lib;%VS_INSTALL_DIR%\PlatformSDK\Lib\AMD64;%VS_INSTALL_DIR%\Common7\Tools;%VS_INSTALL_DIR%\Common7\IDE;%VS_INSTALL_DIR%\Common\Tools;%VS_INSTALL_DIR%\Common\IDE;%VS_INSTALL_DIR%;%VS_INSTALL_DIR%\VC\lib;%PATH%

:end