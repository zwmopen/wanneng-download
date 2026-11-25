@echo off
chcp 65001 >nul
title 万能采集器 · 统一工作台
cd /d "%~dp0"
if exist "%~dp0desktop_shell\万能采集器.exe" (
    start "" "%~dp0desktop_shell\万能采集器.exe"
    exit /b 0
)
if exist "%~dp0config\config.json" (
    set "MATERIAL_HUB_CONFIG=%~dp0config\config.json"
)
where pyw >nul 2>&1
if not errorlevel 1 (
    start "" pyw -3 -m xhs_dl.web.app --app
    exit /b 0
)
where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" pythonw -m xhs_dl.web.app --app
    exit /b 0
)
start "" /min py -3 -m xhs_dl.web.app --app
