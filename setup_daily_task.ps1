param(
    [string]$TaskName = "Personal News Agent",
    [string]$StartTime = "22:00"
)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $ProjectDir "run_daily_agent.ps1"

if (-not (Test-Path $Runner)) {
    throw "Runner script not found: $Runner"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""

$Trigger = New-ScheduledTaskTrigger -Daily -At $StartTime
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Runs the Personal News Agent daily: research at 10 PM, WhatsApp digest at 11 PM." `
    -Force | Out-Null

Write-Host "Scheduled task '$TaskName' created."
Write-Host "Start time: $StartTime daily"
Write-Host "Runner: $Runner"
Write-Host ""
Write-Host "Test it manually from Task Scheduler, or run:"
Write-Host "Start-ScheduledTask -TaskName `"$TaskName`""
