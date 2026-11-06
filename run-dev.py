"""Run the local Django and React servers together; Ctrl+C stops both."""
import os
import signal
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
python = ROOT / ".venv/Scripts/python.exe" if os.name == "nt" else ROOT / ".venv/bin/python"
node = shutil.which("node")
vite = ROOT / "frontend/node_modules/vite/bin/vite.js"
if not python.is_file() or not node or not vite.is_file() or not (ROOT / "backend/.env").is_file():
    raise SystemExit("Project setup is incomplete. Follow README.md first.")
for port in (8000, 5173):
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(f"Port {port} is already in use. Close the existing project server before starting another.")
environment = os.environ.copy()
environment["PYTHONUNBUFFERED"] = "1"
processes = []
child_options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
try:
    processes.append(subprocess.Popen([str(python), str(ROOT / "backend/manage.py"), "runserver", "127.0.0.1:8000"], cwd=ROOT, env=environment, **child_options))
    processes.append(subprocess.Popen([node, str(vite)], cwd=ROOT / "frontend", env=environment, **child_options))
    print("\nDarshan Seva Portal: http://127.0.0.1:5173\nBackend code reloads automatically. Use your existing portal account. Press Ctrl+C to stop both servers.\n", flush=True)
    while all(process.poll() is None for process in processes):
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    for process in processes:
        if process.poll() is None:
            if os.name == "nt":
                # Include Django's reloader child and the virtualenv's Python redirector.
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
    for process in processes:
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
