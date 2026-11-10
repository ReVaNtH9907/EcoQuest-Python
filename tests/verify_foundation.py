"""
EcoQuest Foundation Verification Script
========================================
Runs all 10 verification checks and reports results.
"""

import os
import sys
import importlib
import json

# Project root is one level up from tests/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
RESULTS = []
PASS = 0
FAIL = 0


def record(check_id, name, passed, detail=""):
    global PASS, FAIL
    status = "PASS" if passed else "FAIL"
    if passed:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append({"id": check_id, "name": name, "status": status, "detail": detail})
    icon = "OK" if passed else "FAIL"
    print(f"  [{icon}] {name}" + (f" — {detail}" if detail else ""))


# ============================================================
# CHECK 1: Verify all project directories and files exist
# ============================================================
print("\n=== CHECK 1: Project structure ===")

required_files = [
    "app.py",
    "config.py",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "README.md",
    "routes/__init__.py",
    "routes/main.py",
    "routes/auth.py",
    "routes/dashboard.py",
    "routes/learning.py",
    "routes/missions.py",
    "routes/leaderboard.py",
    "routes/profile.py",
    "models/__init__.py",
    "services/__init__.py",
    "templates/base.html",
    "templates/index.html",
    "templates/errors/404.html",
    "templates/errors/500.html",
    "static/css/style.css",
    "static/js/app.js",
    "tests/__init__.py",
    "tests/test_app.py",
]

required_dirs = [
    "routes",
    "models",
    "services",
    "templates",
    "templates/errors",
    "static",
    "static/css",
    "static/js",
    "static/images",
    "instance",
    "tests",
]

for d in required_dirs:
    full = os.path.join(BASE_DIR, d)
    record("1", f"Directory exists: {d}", os.path.isdir(full))

for f in required_files:
    full = os.path.join(BASE_DIR, f)
    record("1", f"File exists: {f}", os.path.isfile(full))

# ============================================================
# CHECK 2: app.py implements Flask application factory
# ============================================================
print("\n=== CHECK 2: Application factory ===")

try:
    from app import create_app
    record("2", "create_app is importable", True)
except Exception as e:
    record("2", "create_app is importable", False, str(e))

try:
    app = create_app("testing")
    from flask import Flask
    record("2", "create_app returns a Flask instance", isinstance(app, Flask))
except Exception as e:
    record("2", "create_app returns a Flask instance", False, str(e))

# Check that create_app accepts config_name parameter
try:
    dev_app = create_app("development")
    record("2", "create_app('development') works", True)
except Exception as e:
    record("2", "create_app('development') works", False, str(e))

try:
    test_app = create_app("testing")
    record("2", "create_app('testing') works", True)
except Exception as e:
    record("2", "create_app('testing') works", False, str(e))

# ============================================================
# CHECK 3: All Blueprints registered
# ============================================================
print("\n=== CHECK 3: Blueprint registration ===")

app = create_app("testing")

expected_blueprints = {
    "main": "/",
    "auth": "/auth",
    "dashboard": "/dashboard",
    "learning": "/learning",
    "missions": "/missions",
    "leaderboard": "/leaderboard",
    "profile": "/profile",
}

registered = list(app.blueprints.keys())

for bp_name, prefix in expected_blueprints.items():
    record("3", f"Blueprint '{bp_name}' registered", bp_name in registered)

# Check that routes exist under each blueprint
rules = [str(rule) for rule in app.url_map.iter_rules()]
expected_routes = [
    ("/", "main.index"),
    ("/health", "main.health_check"),
    ("/auth/login", "auth.login"),
    ("/auth/register", "auth.register"),
    ("/auth/logout", "auth.logout"),
    ("/dashboard/", "dashboard.overview"),
    ("/learning/", "learning.modules"),
    ("/missions/", "missions.list_missions"),
    ("/leaderboard/", "leaderboard.rankings"),
    ("/profile/", "profile.view_profile"),
]

for route_path, endpoint in expected_routes:
    found = route_path in rules
    record("3", f"Route {route_path} -> {endpoint}", found)

# ============================================================
# CHECK 4: Development and production configuration
# ============================================================
print("\n=== CHECK 4: Configuration ===")

from config import DevelopmentConfig, ProductionConfig, TestingConfig, config_by_name

record("4", "DevelopmentConfig.DEBUG is True", DevelopmentConfig.DEBUG is True)
record("4", "ProductionConfig.DEBUG is False", ProductionConfig.DEBUG is False)
record("4", "TestingConfig.TESTING is True", TestingConfig.TESTING is True)

record("4", "config_by_name has 'development'", "development" in config_by_name)
record("4", "config_by_name has 'production'", "production" in config_by_name)
record("4", "config_by_name has 'testing'", "testing" in config_by_name)

dev_app = create_app("development")
record("4", "Dev app DEBUG is True", dev_app.config["DEBUG"] is True)

test_app = create_app("testing")
record("4", "Test app TESTING is True", test_app.config["TESTING"] is True)
record("4", "Test app uses in-memory SQLite", test_app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:")

# ============================================================
# CHECK 5: SQLite configuration and database connectivity
# ============================================================
print("\n=== CHECK 5: SQLite configuration ===")

dev_app = create_app("development")
db_uri = dev_app.config["SQLALCHEMY_DATABASE_URI"]
record("5", "Database URI contains 'sqlite'", "sqlite" in db_uri)
record("5", "SQLALCHEMY_TRACK_MODIFICATIONS is False",
       dev_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] is False)

# Test that SQLite can actually create a database file
import sqlite3
test_db_path = os.path.join(BASE_DIR, "instance", "verify_test.db")
try:
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)")
    cursor.execute("INSERT INTO test (id) VALUES (1)")
    conn.commit()
    cursor.execute("SELECT id FROM test")
    row = cursor.fetchone()
    conn.close()
    record("5", "SQLite write/read succeeds", row == (1,))
    os.remove(test_db_path)
except Exception as e:
    record("5", "SQLite write/read succeeds", False, str(e))

# ============================================================
# CHECK 6: Environment variables load through python-dotenv
# ============================================================
print("\n=== CHECK 6: Environment variable loading ===")

# Check .env.example has expected keys
env_example_path = os.path.join(BASE_DIR, ".env.example")
with open(env_example_path, "r") as f:
    env_content = f.read()

expected_env_keys = [
    "FLASK_ENV",
    "SECRET_KEY",
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "AI_SERVICE_API_KEY",
]

for key in expected_env_keys:
    record("6", f".env.example contains {key}", key in env_content)

# Check that python-dotenv is in requirements.txt
req_path = os.path.join(BASE_DIR, "requirements.txt")
with open(req_path, "r") as f:
    req_content = f.read()
record("6", "python-dotenv in requirements.txt", "python-dotenv" in req_content)

# Check that config.py calls load_dotenv
config_path = os.path.join(BASE_DIR, "config.py")
with open(config_path, "r") as f:
    config_content = f.read()
record("6", "config.py imports load_dotenv", "load_dotenv" in config_content)
record("6", "config.py calls load_dotenv()", "load_dotenv()" in config_content)

# Check config reads from os.environ
record("6", "Config reads SECRET_KEY from os.environ",
       'os.environ.get("SECRET_KEY"' in config_content or
       "os.environ.get('SECRET_KEY'" in config_content)

# ============================================================
# CHECK 7: Secrets are not hardcoded
# ============================================================
print("\n=== CHECK 7: No hardcoded secrets ===")

# Scan all Python files for suspicious patterns
import re
suspicious_patterns = [
    (r'(?i)password\s*=\s*["\'][^"\']+["\']', "hardcoded password"),
    (r'(?i)api_key\s*=\s*["\'][a-zA-Z0-9]{16,}["\']', "hardcoded API key"),
    (r'(?i)secret\s*=\s*["\'][a-zA-Z0-9]{16,}["\']', "hardcoded secret"),
]

py_files = []
for root, dirs, files in os.walk(BASE_DIR):
    dirs[:] = [d for d in dirs if d not in ("venv", ".venv", "__pycache__", ".pytest_cache")]
    for f in files:
        if f.endswith(".py"):
            py_files.append(os.path.join(root, f))

hardcoded_found = []
for filepath in py_files:
    with open(filepath, "r") as f:
        content = f.read()
    for pattern, desc in suspicious_patterns:
        matches = re.findall(pattern, content)
        if matches:
            rel = os.path.relpath(filepath, BASE_DIR)
            hardcoded_found.append(f"{rel}: {desc}")

record("7", "No hardcoded passwords/keys in Python files",
       len(hardcoded_found) == 0,
       "; ".join(hardcoded_found) if hardcoded_found else "")

# Check .gitignore excludes .env
gitignore_path = os.path.join(BASE_DIR, ".gitignore")
with open(gitignore_path, "r") as f:
    gitignore = f.read()
record("7", ".gitignore excludes .env", ".env" in gitignore)
record("7", ".gitignore excludes venv/", "venv/" in gitignore)
record("7", ".gitignore excludes *.db", "*.db" in gitignore)
record("7", ".gitignore excludes __pycache__/", "__pycache__/" in gitignore)
record("7", ".gitignore excludes instance/", "instance/" in gitignore)

# Config uses os.environ.get, not raw strings for secrets
record("7", "SECRET_KEY reads from env var",
       'os.environ.get("SECRET_KEY"' in config_content)
record("7", "SUPABASE_URL reads from env var",
       'os.environ.get("SUPABASE_URL"' in config_content)
record("7", "AI_SERVICE_API_KEY reads from env var",
       'os.environ.get("AI_SERVICE_API_KEY"' in config_content)

# ============================================================
# CHECK 8: 404 and 500 error handlers
# ============================================================
print("\n=== CHECK 8: Error handlers ===")

app = create_app("testing")
client = app.test_client()

# 404 test
resp = client.get("/this-route-does-not-exist")
record("8", "404 handler returns status 404", resp.status_code == 404)
record("8", "404 response contains HTML", b"404" in resp.data)

# 500 test — need a fresh app with a crash route added before first request
app_500 = create_app("testing")
app_500.config["TESTING"] = False
app_500.config["PROPAGATE_EXCEPTIONS"] = False

@app_500.route("/force-500-verify")
def force_500():
    raise Exception("Verification 500 error")

client_500 = app_500.test_client()
resp = client_500.get("/force-500-verify")
record("8", "500 handler returns status 500", resp.status_code == 500)
record("8", "500 response contains HTML", b"500" in resp.data)

# Check error templates extend base.html
for err_file in ["templates/errors/404.html", "templates/errors/500.html"]:
    with open(os.path.join(BASE_DIR, err_file), "r") as f:
        content = f.read()
    record("8", f"{err_file} extends base.html", 'extends "base.html"' in content)

# ============================================================
# CHECK 9: Import errors and circular dependencies
# ============================================================
print("\n=== CHECK 9: Import checks ===")

modules_to_check = [
    "config",
    "app",
    "routes",
    "routes.main",
    "routes.auth",
    "routes.dashboard",
    "routes.learning",
    "routes.missions",
    "routes.leaderboard",
    "routes.profile",
    "models",
    "services",
]

for mod in modules_to_check:
    try:
        importlib.import_module(mod)
        record("9", f"Import {mod}", True)
    except Exception as e:
        record("9", f"Import {mod}", False, str(e))

# Circular dependency: try creating app multiple times
try:
    a1 = create_app("testing")
    a2 = create_app("development")
    a3 = create_app("testing")
    record("9", "No circular dependency (3 sequential create_app calls)", True)
except Exception as e:
    record("9", "No circular dependency", False, str(e))

# ============================================================
# CHECK 10: Flask dev server test + homepage
# ============================================================
print("\n=== CHECK 10: Server and homepage ===")

app = create_app("development")
client = app.test_client()

resp = client.get("/")
record("10", "GET / returns 200", resp.status_code == 200)
record("10", "Homepage contains 'EcoQuest'", b"EcoQuest" in resp.data)
record("10", "Homepage is HTML (rendered from template)", b"<!DOCTYPE html>" in resp.data or b"<html" in resp.data)

resp = client.get("/health")
record("10", "GET /health returns 200", resp.status_code == 200)
data = resp.get_json()
record("10", "Health check returns JSON {status: ok}", data and data.get("status") == "ok")

# Test all blueprint placeholder endpoints return 200
blueprint_endpoints = [
    "/auth/login",
    "/auth/register",
    "/auth/logout",
    "/dashboard/",
    "/learning/",
    "/missions/",
    "/leaderboard/",
    "/profile/",
]

for ep in blueprint_endpoints:
    resp = client.get(ep, follow_redirects=True)
    record("10", f"GET {ep} returns 200", resp.status_code == 200)

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print(f"  TOTAL: {PASS + FAIL}  |  PASSED: {PASS}  |  FAILED: {FAIL}")
print("=" * 60)

if FAIL > 0:
    print("\nFailed checks:")
    for r in RESULTS:
        if r["status"] == "FAIL":
            detail = f" — {r['detail']}" if r["detail"] else ""
            print(f"  [FAIL] Check {r['id']}: {r['name']}{detail}")

sys.exit(0 if FAIL == 0 else 1)
