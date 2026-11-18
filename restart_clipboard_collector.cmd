@echo off
title Universal Clipboard Collector Restart
chcp 65001 >nul
cd /d "%~dp0"
"C:\Users\z\AppData\Local\Programs\Python\Python311\python.exe" "%~dp0restart_clipboard_collector.py"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXIT_CODE%
