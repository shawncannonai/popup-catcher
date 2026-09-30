# popup-catcher

A black console window flashes up on your Windows desktop and disappears before
you can read its title. It happens again an hour later. Something scheduled is
doing it, but Task Scheduler, Event Viewer and Process Explorer can't tell you
which job.

popup-catcher answers that. It watches for new console processes (`cmd`,
`powershell`, `python`, `node`, `bash`, `git` and others) whose parent chain has
no interactive shell. When it finds one, it:

1. **hides the window straight away** (`SW_HIDE`), including the Windows
   Terminal window that Windows 11 opens for it, and
2. **logs the whole parent chain**, so you know which script to fix.

```
> python popup_catcher.py --report
  41  pythonw.exe C:\ops\mail\watcher.py        (last 2026-09-24T14:02:11, windows hidden 41)
   6  wscript.exe C:\ops\run_hidden.vbs backup  (last 2026-09-24T09:00:03, windows hidden 6)
```

Your own terminals descend from `explorer`, Windows Terminal, VS Code or another
IDE, so it never touches them.

## Why a window pops up at all

A console program gets a **new** visible window only when its *direct* parent
has no console: `pythonw`, `wscript`, a service or a scheduled task. If the
parent is `python.exe` or `powershell.exe`, the child inherits that parent's
console (hidden or not) and never pops. The usual culprit is a windowless script
calling `subprocess.run([...])` without `creationflags=CREATE_NO_WINDOW`.

On Windows 11 there's a second catch. When Windows Terminal is the default
terminal, the visible window belongs to `WindowsTerminal.exe`, not to the child
process. Hiding the child's own windows then hides nothing. popup-catcher treats
a new Terminal window that appears within 5 seconds of a background console spawn
as that spawn's window and hides it too.

## Install

```powershell
pip install psutil
powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1   # runs at logon, under pythonw
powershell -NoProfile -ExecutionPolicy Bypass -File selftest_task.ps1   # proves it end to end
python popup_catcher.py --report
```

The log is `state/popups.jsonl`. Each line records the process, its command
line, the spawner and the window titles it hid.

## Fixing the source

The report tells you which script is responsible. For Python, add
`creationflags=subprocess.CREATE_NO_WINDOW` to the `subprocess` call. For
scheduled tasks, launch through `pythonw` or a hidden VBS wrapper. Hiding the
window is the stopgap; the log is how you get the real fix.

## Limits

- Windows only. Needs Python 3.10+ and `psutil`.
- It polls twice a second, so a window can be visible for up to about half a
  second before it is hidden.
- Running without elevation, it can't read the command lines of elevated
  processes. They are logged by name.

MIT licensed.
