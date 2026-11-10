"""
EcoQuest — Design System Verification
======================================
Tests that all templates render, components are present,
CSS/JS files exist, and no backend routes were broken.
"""

import os
import sys
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import create_app

PASS = 0
FAIL = 0
RESULTS = []


def record(name, passed, detail=""):
    global PASS, FAIL
    if passed:
        PASS += 1
    else:
        FAIL += 1
    icon = "OK" if passed else "FAIL"
    RESULTS.append({"name": name, "passed": passed, "detail": detail})
    print(f"  [{icon}] {name}" + (f" — {detail}" if detail else ""))


app = create_app("testing")
client = app.test_client()


# ============================================================
# 1. FILE STRUCTURE
# ============================================================
print("\n=== Files & Directories ===")

required = [
    "static/css/style.css",
    "static/js/app.js",
    "templates/base.html",
    "templates/index.html",
    "templates/errors/404.html",
    "templates/errors/500.html",
    "templates/components/macros.html",
    "templates/components/navbar.html",
    "templates/components/footer.html",
]

for f in required:
    full = os.path.join(BASE_DIR, f)
    record(f"File exists: {f}", os.path.isfile(full))


# ============================================================
# 2. CSS DESIGN SYSTEM CONTENTS
# ============================================================
print("\n=== CSS Design System ===")

css_path = os.path.join(BASE_DIR, "static", "css", "style.css")
with open(css_path, "r", encoding="utf-8") as fh:
    css = fh.read()

# Check custom properties / tokens
css_tokens = [
    ("--color-primary", "Brand primary colour"),
    ("--color-primary-dark", "Brand dark green"),
    ("--color-primary-light", "Brand light green"),
    ("--color-bg", "Background colour"),
    ("--color-text", "Main text colour"),
    ("--color-text-secondary", "Secondary text colour"),
    ("--color-border", "Border colour"),
    ("--font-sans", "Font family token"),
    ("--radius-md", "Border radius token"),
    ("--shadow-md", "Shadow token"),
    ("--transition-base", "Transition token"),
    ("--nav-height", "Navbar height token"),
]

for token, desc in css_tokens:
    record(f"CSS token: {token}", token in css, desc)

# Check colour values
colour_checks = [
    ("#059669", "Primary green"),
    ("#047857", "Dark green"),
    ("#ECFDF5", "Light green"),
    ("#F8FAFC", "Background"),
    ("#111827", "Main text"),
    ("#64748B", "Secondary text"),
    ("#E2E8F0", "Border"),
]

for colour, desc in colour_checks:
    record(f"Colour value: {colour}", colour in css, desc)

# Check component sections
component_selectors = [
    (".btn", "Buttons"),
    (".btn-primary", "Primary button"),
    (".btn-secondary", "Secondary button"),
    (".btn-outline", "Outline button"),
    (".btn-ghost", "Ghost button"),
    (".navbar", "Navigation bar"),
    (".navbar-brand", "Navbar brand / logo"),
    (".navbar-toggle", "Mobile nav toggle"),
    (".navbar-menu-mobile", "Mobile menu"),
    (".card", "Card"),
    (".card-interactive", "Interactive card hover"),
    (".form-input", "Input field"),
    (".form-select", "Select dropdown"),
    (".badge", "Badge"),
    (".xp-display", "XP indicator"),
    (".progress", "Progress bar"),
    (".modal-overlay", "Modal overlay"),
    (".modal", "Modal"),
    (".toast-container", "Toast container"),
    (".toast", "Toast notification"),
    (".section-header", "Section heading"),
    (".footer", "Footer"),
    (".flash", "Flash messages"),
]

for selector, desc in component_selectors:
    # Match as a CSS selector (class name at start of rule)
    record(f"CSS component: {selector}", selector in css, desc)

# Responsive
record("Responsive: @media", "@media" in css)
record("Responsive: max-width: 768px", "max-width: 768px" in css)


# ============================================================
# 3. JAVASCRIPT
# ============================================================
print("\n=== JavaScript ===")

js_path = os.path.join(BASE_DIR, "static", "js", "app.js")
with open(js_path, "r", encoding="utf-8") as fh:
    js = fh.read()

js_features = [
    ("navbar-toggle", "Mobile nav toggle handler"),
    ("openModal", "Modal open function"),
    ("closeModal", "Modal close function"),
    ("showToast", "Toast notification function"),
    ("Escape", "Escape key handler"),
    ("is-dismissing", "Toast dismiss animation"),
    ("aria-expanded", "ARIA accessibility"),
]

for term, desc in js_features:
    record(f"JS feature: {term}", term in js, desc)


# ============================================================
# 4. TEMPLATE RENDERING
# ============================================================
print("\n=== Template Rendering ===")

# Homepage
resp = client.get("/")
html = resp.data.decode("utf-8")
record("Homepage returns 200", resp.status_code == 200)
record("Homepage contains DOCTYPE", "<!DOCTYPE html>" in html)
record("Homepage contains Inter font link", "fonts.googleapis.com" in html and "Inter" in html)
record("Homepage contains style.css link", "style.css" in html)
record("Homepage contains app.js link", "app.js" in html)

# Navigation elements
record("Navbar rendered: .navbar", 'class="navbar"' in html)
record("Navbar rendered: brand link", "navbar-brand" in html)
record("Navbar rendered: desktop links", "navbar-links" in html)
record("Navbar rendered: auth buttons", "navbar-auth" in html)
record("Navbar rendered: mobile toggle", "navbar-toggle" in html)
record("Navbar rendered: mobile menu", "navbar-mobile" in html)

# Footer elements
record("Footer rendered: .footer", 'class="footer"' in html)
record("Footer rendered: footer-brand", "footer-brand" in html)
record("Footer rendered: tagline", "Change the Planet" in html)
record("Footer rendered: footer-grid", "footer-grid" in html)
record("Footer rendered: footer links", "footer-links" in html)
record("Footer rendered: footer-bottom", "footer-bottom" in html)

# Component macros
record("Component: buttons rendered", "btn btn-primary" in html)
record("Component: badges rendered", "badge badge-success" in html)
record("Component: XP display rendered", "xp-display" in html)
record("Component: progress bar rendered", "progress-bar" in html)
record("Component: section header rendered", "section-header" in html)
record("Component: toast container rendered", "toast-container" in html)

# Verify macro library renders card, form controls, and modal components
from flask import render_template_string
with app.test_request_context():
    rendered_macros = render_template_string("""
        {% from "components/macros.html" import card, form_input, form_select, modal %}
        {% call card(title="Test", interactive=true) %}<p>Body</p>{% endcall %}
        {{ form_input("test_input", label="Input") }}
        {{ form_select("test_select", options=[{"value":"1", "label":"One"}]) }}
        {% call modal("test-modal", title="Modal") %}<p>Content</p>{% endcall %}
    """)
    record("Component: cards rendered", "card card-interactive" in rendered_macros)
    record("Component: form input rendered", "form-input" in rendered_macros)
    record("Component: form select rendered", "form-select" in rendered_macros)
    record("Component: modal rendered", "modal-overlay" in rendered_macros)

# ARIA / Accessibility
record("Accessibility: nav role", 'role="navigation"' in html)
record("Accessibility: main element", "<main" in html)
record("Accessibility: footer role", 'role="contentinfo"' in html)
record("Accessibility: aria-label on toggle", 'aria-label="Toggle navigation menu"' in html)
record("Accessibility: aria-live on toasts", 'aria-live="polite"' in html)


# ============================================================
# 5. ERROR PAGES
# ============================================================
print("\n=== Error Pages ===")

resp_404 = client.get("/nonexistent-page")
html_404 = resp_404.data.decode("utf-8")
record("404 returns status 404", resp_404.status_code == 404)
record("404 uses design system (navbar)", "navbar" in html_404)
record("404 uses design system (footer)", "footer" in html_404)
record("404 has back-to-home button", "btn btn-primary" in html_404)

# 500 test — use a fresh app before any requests are made
app_500 = create_app("testing")
app_500.config["TESTING"] = False
app_500.config["PROPAGATE_EXCEPTIONS"] = False

@app_500.route("/force-500-ds")
def force_500_ds():
    raise Exception("Design system 500 test")

client2 = app_500.test_client()
resp_500 = client2.get("/force-500-ds")
html_500 = resp_500.data.decode("utf-8")
record("500 returns status 500", resp_500.status_code == 500)
record("500 uses design system (navbar)", "navbar" in html_500)
record("500 has back-to-home button", "btn btn-primary" in html_500)


# ============================================================
# 6. BACKEND ROUTES UNMODIFIED
# ============================================================
print("\n=== Backend Routes Intact ===")

# Reset to testing config for clean client
app2 = create_app("testing")
client3 = app2.test_client()

routes = [
    ("/", 200),
    ("/health", 200),
    ("/auth/login", 200),
    ("/auth/register", 200),
    ("/auth/logout", 200),
    ("/dashboard/", 200),
    ("/learning/", 200),
    ("/missions/", 200),
    ("/leaderboard/", 200),
    ("/profile/", 200),
]

for path, expected in routes:
    resp = client3.get(path, follow_redirects=True)
    record(f"Route {path} -> {expected}", resp.status_code == expected)


# ============================================================
# 7. STATIC FILE SERVING
# ============================================================
print("\n=== Static File Serving ===")

css_resp = client3.get("/static/css/style.css")
record("GET /static/css/style.css -> 200", css_resp.status_code == 200)
record("CSS content-type", "text/css" in css_resp.content_type)

js_resp = client3.get("/static/js/app.js")
record("GET /static/js/app.js -> 200", js_resp.status_code == 200)
record("JS served successfully", js_resp.status_code == 200)


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print(f"  TOTAL: {PASS + FAIL}  |  PASSED: {PASS}  |  FAILED: {FAIL}")
print("=" * 60)

if FAIL > 0:
    print("\nFailed checks:")
    for r in RESULTS:
        if not r["passed"]:
            detail = f" — {r['detail']}" if r["detail"] else ""
            print(f"  [FAIL] {r['name']}{detail}")

if __name__ == "__main__":
    sys.exit(0 if FAIL == 0 else 1)
