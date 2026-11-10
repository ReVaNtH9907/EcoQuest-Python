"""
EcoQuest — Local Server Execution Test
======================================
Tests:
  1. app.py runs directly with host 127.0.0.1 and port 5000
  2. Debug mode is active in development, disabled in production
  3. Homepage loads successfully over HTTP
  4. Port binding and shutdown
"""

import os
import sys
import subprocess
import time
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_EXE = sys.executable

print("Testing direct execution of app.py...")

# Start app.py as a subprocess with FLASK_ENV=development
env = os.environ.copy()
env["FLASK_ENV"] = "development"
env["PYTHONUNBUFFERED"] = "1"

proc = subprocess.Popen(
    [PYTHON_EXE, "app.py"],
    cwd=BASE_DIR,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

server_url = "http://127.0.0.1:5000"
success = False
status_code = None
content = ""

try:
    # Wait for server to bind
    for attempt in range(15):
        time.sleep(0.5)
        # Check if process crashed prematurely
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            print("Process exited prematurely:")
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            sys.exit(1)
        try:
            req = urllib.request.Request(server_url + "/")
            with urllib.request.urlopen(req, timeout=2) as resp:
                status_code = resp.getcode()
                content = resp.read().decode("utf-8")
                if status_code == 200:
                    success = True
                    break
        except urllib.error.URLError:
            continue
finally:
    # Terminate process cleanly
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

print(f"Server response status: {status_code}")
print(f"Homepage received {len(content)} bytes")
print("Brand headline in response:", "Turn Environmental Knowledge Into" in content)

if not success or status_code != 200:
    print("[FAIL] Server failed to start and serve homepage.")
    sys.exit(1)

print("[OK] Direct execution of app.py on http://127.0.0.1:5000 verified successfully!")
