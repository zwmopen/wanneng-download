$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $projectRoot "XHS-Clipboard-Collector.vbs"
$config = Join-Path $projectRoot "config\config.json"
$wscript = Join-Path $env:WINDIR "System32\wscript.exe"
$arguments = "//B //Nologo `"$launcher`""
$taskName = "Universal-Clipboard-Collector"

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "项目启动器不存在：$launcher"
}
if (-not (Test-Path -LiteralPath $config)) {
    throw "本机配置不存在：$config"
}

function Set-CollectorShortcut([string]$Path, [string]$Description) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $wscript
    $shortcut.Arguments = $arguments
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.Description = $Description
    $shortcut.WindowStyle = 7
    $shortcut.Save()
}

$startupFolder = [Environment]::GetFolderPath("Startup")
$desktopFolder = [Environment]::GetFolderPath("Desktop")
Set-CollectorShortcut (Join-Path $startupFolder "Universal-Clipboard-Collector.lnk") "万能素材剪贴板采集（项目仓库启动器）"
Set-CollectorShortcut (Join-Path $desktopFolder "启动万能素材剪贴板采集.lnk") "万能素材剪贴板采集（项目仓库启动器）"

$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$runValue = "`"$wscript`" $arguments"
Set-ItemProperty -Path $runKey -Name $taskName -Value $runValue -Force

$action = New-ScheduledTaskAction -Execute $wscript -Argument $arguments -WorkingDirectory $projectRoot
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Set-ScheduledTask -TaskName $taskName -Action $action | Out-Null
} else {
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -Priority 7
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings | Out-Null
}

Write-Output "Collector autostart now targets the xhs-dl project launcher."
Write-Output "Startup shortcut: $(Join-Path $startupFolder 'Universal-Clipboard-Collector.lnk')"
Write-Output "Desktop shortcut: $(Join-Path $desktopFolder '启动万能素材剪贴板采集.lnk')"
Write-Output "Scheduled task: $taskName"
