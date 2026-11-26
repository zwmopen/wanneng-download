@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "WRANGLER_CMD="
where wrangler >nul 2>nul && set "WRANGLER_CMD=wrangler"
if "%WRANGLER_CMD%"=="" if exist "D:\AICode\工具开发\projects\second-brain-dashi\node_modules\.bin\wrangler.cmd" (
  set "WRANGLER_CMD=D:\AICode\工具开发\projects\second-brain-dashi\node_modules\.bin\wrangler.cmd"
)
if "%WRANGLER_CMD%"=="" (
  set "WRANGLER_CMD=npx wrangler"
)

echo [1/4] 检查 Cloudflare 登录状态...
call %WRANGLER_CMD% whoami >nul 2>nul
if errorlevel 1 (
  echo 当前未登录或授权已过期，正在打开浏览器进行 Cloudflare 授权...
  call %WRANGLER_CMD% login
  if errorlevel 1 (
    echo [错误] Cloudflare 登录未完成，请先登录后重试。
    pause
    exit /b 1
  )
)

echo [2/4] 部署抖音云端解析 Worker (wanneng-douyin-api)...
pushd "%~dp0douyin-parser"
call %WRANGLER_CMD% deploy
popd

echo [3/4] 部署 403 防盗链转发 Worker (wanneng-media-proxy)...
pushd "%~dp0media-proxy"
call %WRANGLER_CMD% deploy
popd

echo [4/4] 部署完成！请复制上方输出的两个 https://*.workers.dev 地址，填入桌面端/手机端设置中的「云端兜底与 403 转发」即可。
pause
