"""Popup catcher: find and hide console windows that background jobs pop onto the operator's desktop.

Design note, 2026-09-24: "getting tired of those [popup terminals] happening that needs to stop too." The usual fix already
wraps scheduled tasks (run_hidden.vbs); what still leaks is a HIDDEN parent (pythonw, wscript, a service) spawning a
CONSOLE child (powershell, cmd, python.exe, claude.exe) without CREATE_NO_WINDOW, which gets a brand-new visible
window. Nothing recorded WHO did it, so nothing could be fixed.

Every second: new console-type processes whose ancestry has no interactive shell (explorer, a terminal, Claude Code,
an IDE) are logged with the full parent chain to state/popups.jsonl, and any visible top-level window they own is
hidden (SW_HIDE) at once. A person's own terminals descend from explorer/WindowsTerminal and are never touched.

Run silently at logon:  pythonw popup_catcher.py      Report:  python popup_catcher.py --report
"""
import ctypes
import json
import sys
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
STATE = HERE / "state"
LOG = STATE / "popups.jsonl"
CONSOLE = {"powershell.exe", "pwsh.exe", "cmd.exe", "python.exe", "py.exe", "node.exe", "claude.exe", "conhost.exe",
           "bash.exe", "wsl.exe", "git.exe"}
INTERACTIVE = {"explorer.exe", "windowsterminal.exe", "openconsole.exe", "code.exe", "claude.exe", "cursor.exe",
               "powershell_ise.exe", "devenv.exe", "idea64.exe"}
CONSOLELESS = {"pythonw.exe", "wscript.exe", "cscript.exe", "svchost.exe", "taskhostw.exe", "services.exe",
               "taskeng.exe", "mshta.exe", "rundll32.exe"}
HIDDEN_PARENTS = CONSOLELESS | {"node.exe", "python.exe"}  # used only to name the spawner in the log
user32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def windows_of(pids: set[int]) -> list[tuple[int, str]]:
    found = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids:
                n = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return found


def terminal_windows() -> dict[int, str]:
    """Visible Windows Terminal top-level windows. On Windows 11 a console child with no console parent is hosted by
    Windows Terminal (the default terminal), so its window belongs to WindowsTerminal.exe, not to the child; found
    2026-09-24 when the self-test logged the spawn but hid nothing."""
    found = {}

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            if cls.value == "CASCADIA_HOSTING_WINDOW_CLASS":
                n = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                found[hwnd] = buf.value
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return found


def chain(p: psutil.Process) -> list[dict]:
    out = []
    try:
        for a in [p] + p.parents():
            try:
                out.append({"pid": a.pid, "name": a.name(), "cmd": " ".join(a.cmdline())[:240]})
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                out.append({"pid": a.pid, "name": "?", "cmd": ""})
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass
    return out


def is_background(ch: list[dict]) -> bool:
    """A console child gets a NEW window only when its DIRECT parent has no console (pythonw, wscript, a service).
    A child of python.exe/powershell.exe inherits that parent's console, hidden or not, and never pops (2026-09-24:
    a mail watcher's venv python -> python was logged as a popup and was not one)."""
    names = [c["name"].lower() for c in ch[1:]]
    if any(n in INTERACTIVE for n in names):
        return False
    return names[0] in CONSOLELESS


def report() -> int:
    if not LOG.exists():
        print("no popups recorded")
        return 0
    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    by = {}
    for r in rows:
        key = r["spawner"]
        by.setdefault(key, []).append(r)
    for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(v):4d}  {k}   (last {v[-1]['t']}, windows hidden {sum(len(x['hidden']) for x in v)})")
    return 0


def main() -> int:
    if "--report" in sys.argv:
        return report()
    STATE.mkdir(parents=True, exist_ok=True)
    seen = {p.pid for p in psutil.process_iter()}
    watch: dict[int, dict] = {}                         # background console pid -> its log row, re-checked for windows
    known_wt = set(terminal_windows())
    last_bg = 0.0                                       # time of the last background console spawn
    while True:
        now = {p.pid: p for p in psutil.process_iter(["name"])}
        for pid in set(now) - seen:
            p = now[pid]
            if (p.info.get("name") or "").lower() not in CONSOLE:
                continue
            ch = chain(p)
            if len(ch) < 2 or not is_background(ch):
                continue
            spawner = next((c["cmd"] or c["name"] for c in ch[1:] if c["name"].lower() in HIDDEN_PARENTS | {"python.exe"}
                            and c["cmd"]), ch[1]["name"])
            watch[pid] = {"t": datetime.now().isoformat(timespec="seconds"), "pid": pid, "name": ch[0]["name"],
                          "cmd": ch[0]["cmd"], "spawner": spawner[:200], "chain": ch, "hidden": []}
            last_bg = time.time()
        seen = set(now)
        # A Windows Terminal window that appears within 5 s of a background console spawn is that spawn's window.
        wt = terminal_windows()
        for hwnd in set(wt) - known_wt:
            if time.time() - last_bg <= 5 and watch:
                user32.ShowWindow(hwnd, 0)
                for row in watch.values():
                    row["hidden"].append("WT: " + wt[hwnd][:110])
        known_wt = set(wt)
        for pid, row in list(watch.items()):
            if pid not in now:                           # exited: write what we saw, stop watching
                with LOG.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row) + "\n")
                del watch[pid]
                continue
            for hwnd, title in windows_of({pid} | {c.pid for c in _children(pid)}):
                user32.ShowWindow(hwnd, 0)               # SW_HIDE
                row["hidden"].append(title[:120])
        time.sleep(0.5)


def _children(pid: int):
    try:
        return psutil.Process(pid).children(recursive=True)
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return []


if __name__ == "__main__":
    sys.exit(main())
