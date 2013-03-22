@echo off
echo JumpStart! v0.1 by Scotch   
echo.   
echo Your desktop is being restored, Please wait. . .   
ping -n 5 127.0.0.1 > NUL 2>&1   
echo Killing process Explorer.exe. . .   
taskkill /f /im explorer.exe   
cls   
echo Success!   
echo.   
echo Your desktop is now loading. . .   
ping -n 5 127.0.0.1 > NUL 2>&1   
echo.   
ping -n 5 127.0.0.1 > NUL 2>&1   
start C:\Windows\explorer.exe   
EXIT

