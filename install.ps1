# Register a scheduled task that runs popup_catcher.py with pythonw (no window) at logon, and start it now.
# Battery-friendly, restarts on failure, never overlaps itself.
#
#     powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
param([string]$TaskName = "PopupCatcher")
$py = (Get-Command pythonw.exe -ErrorAction Stop).Source
$dir = $PSScriptRoot
$act = New-ScheduledTaskAction -Execute $py -Argument "`"$dir\popup_catcher.py`"" -WorkingDirectory $dir
$trig = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $act -Trigger $trig -Settings $set -Description "Logs and hides console windows spawned by background jobs (popup_catcher.py)" -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 3
$t = Get-ScheduledTask -TaskName $TaskName
"state {0}; exe {1}" -f $t.State, $t.Actions[0].Execute
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'popup_catcher' } | ForEach-Object { "running pid $($_.ProcessId)" }
