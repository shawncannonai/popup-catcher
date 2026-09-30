# End-to-end proof: launch selftest.py from Task Scheduler (a true background parent), then print the report.
# The catcher must log selftest.py as the spawner and hide the cmd.exe window it pops.
$pyw = (Get-Command pythonw.exe -ErrorAction Stop).Source
$py = (Get-Command python.exe -ErrorAction Stop).Source
$dir = $PSScriptRoot
$act = New-ScheduledTaskAction -Execute $pyw -Argument "`"$dir\selftest.py`""
$set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName PopupCatcher-SelfTest -Action $act -Settings $set -Force | Out-Null
Start-ScheduledTask -TaskName PopupCatcher-SelfTest
Start-Sleep -Seconds 10
Unregister-ScheduledTask -TaskName PopupCatcher-SelfTest -Confirm:$false
& $py "$dir\popup_catcher.py" --report
Get-Content "$dir\state\popups.jsonl" -Tail 1 -ErrorAction SilentlyContinue
