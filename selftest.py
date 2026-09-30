"""Self-test: a windowless parent (run this with pythonw) spawns a console child WITHOUT CREATE_NO_WINDOW, exactly
the leak the catcher exists for. The catcher must log it with this file as the spawner and hide its window.
    pythonw selftest.py ; then  python popup_catcher.py --report"""
import subprocess
subprocess.run(["cmd.exe", "/c", "ping -n 6 127.0.0.1 >nul"])
