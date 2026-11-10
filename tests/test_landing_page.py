"""
EcoQuest — Landing Page Verification Test Suite
================================================
Verifies that the landing page meets all requirements:
  - Navigation bar structure and links
  - Hero section headline, description, CTAs, and dashboard preview
  - Problem section headline and copy
  - How It Works 6-step cards
  - Featured missions (3 cards with images, tags, XP, CTAs)
  - Impact section with 4 stats and prototype data disclosure
  - Final CTA section
  - Footer with branding, links, contact, copyright
  - All button routes resolve properly
  - Static images and CSS files are properly served
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


def record(section, name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
    icon = "OK" if condition else "FAIL"
    RESULTS.append({"section": section, "name": name, "passed": condition, "detail": detail})
    print(f"  [{icon}] ({section}) {name}" + (f" — {detail}" if detail else ""))


app = create_app("testing")
client = app.test_client()

resp = client.get("/")
html = resp.data.decode("utf-8")

# ============================================================
# 1. NAVIGATION BAR
# ============================================================
print("\n=== 1. Navigation Bar ===")
record("Navbar", "EcoQuest brand present", "EcoQuest" in html)
record("Navbar", "Home link present", 'href="/"' in html or ">Home<" in html)
record("Navbar", "Learn link present", ">Learn<" in html)
record("Navbar", "Missions link present", ">Missions<" in html)
record("Navbar", "Impact link present", ">Impact<" in html and "#impact" in html)
record("Navbar", "Leaderboard link present", ">Leaderboard<" in html)
record("Navbar", "Login button present", ">Log in<" in html)
record("Navbar", "Sign Up button present", ">Sign Up<" in html)
record("Navbar", "Mobile hamburger toggle present", 'id="navbar-toggle"' in html)

# ============================================================
# 2. HERO SECTION
# ============================================================
print("\n=== 2. Hero Section ===")
record("Hero", "Exact Headline present", "Turn Environmental Knowledge Into" in html and "Real-World Action." in html)
record("Hero", "Exact Description present", "Learn practical eco concepts, complete hands-on missions, upload proof, verify your impact, and compete with your community." in html)
record("Hero", "CTA button: Start Your Eco Journey", "Start Your Eco Journey" in html)
record("Hero", "CTA button: Explore Missions", "Explore Missions" in html)
record("Hero", "Dashboard Preview container present", "preview-card" in html)
record("Hero", "Dashboard Preview: Verified missions metric", "Verified Missions" in html and "18" in html)
record("Hero", "Dashboard Preview: XP earned metric", "XP Earned" in html and "2,450" in html)
record("Hero", "Dashboard Preview: Waste collected metric", "Waste Collected" in html and "42.5 kg" in html)
record("Hero", "Dashboard Preview: Trees planted metric", "Trees Planted" in html and "14" in html)

# ============================================================
# 3. PROBLEM SECTION
# ============================================================
print("\n=== 3. Problem Section ===")
record("Problem", "Exact Headline present", 
       "Awareness Alone Isn't Enough." in html or "Awareness Alone Isn&#39;t Enough." in html)
record("Problem", "Explains participation requirement", "require" in html.lower() or "passive awareness" in html.lower())
record("Problem", "Dilemma and Solution cards present", "card-dilemma" in html and "card-solution" in html)

# ============================================================
# 4. HOW IT WORKS (6 STEPS)
# ============================================================
print("\n=== 4. How It Works ===")
record("How It Works", "Section header present", "How EcoQuest Works" in html)
record("How It Works", "Step 1: Learn", "1. Learn" in html and "Discover" in html)
record("How It Works", "Step 2: Act", "2. Act" in html and "missions" in html.lower())
record("How It Works", "Step 3: Verify", "3. Verify" in html and "proof" in html.lower())
record("How It Works", "Step 4: Earn", "4. Earn" in html and "XP" in html)
record("How It Works", "Step 5: Compete", "5. Compete" in html and "leaderboard" in html.lower())
record("How It Works", "Step 6: Impact", "6. Impact" in html and "environmental" in html.lower())
record("How It Works", "Six step cards rendered", html.count("step-card") == 6)

# ============================================================
# 5. FEATURED MISSIONS
# ============================================================
print("\n=== 5. Featured Missions ===")
record("Missions", "Mission 1: Clean a Public Area", "Clean a Public Area" in html)
record("Missions", "Mission 2: Plant a Native Tree", "Plant a Native Tree" in html)
record("Missions", "Mission 3: Collect Recyclable Waste", "Collect Recyclable Waste" in html)
record("Missions", "Mission 1 media image linked", "mission-cleanup.svg" in html)
record("Missions", "Mission 2 media image linked", "mission-tree.svg" in html)
record("Missions", "Mission 3 media image linked", "mission-recycling.svg" in html)
record("Missions", "Mission difficulties displayed", "Intermediate" in html and "Moderate" in html and "Beginner" in html)
record("Missions", "Mission XP rewards displayed", "150 XP" in html and "250 XP" in html and "100 XP" in html)
record("Missions", "Explore All Missions button present", "Explore All Missions" in html)

# ============================================================
# 6. ENVIRONMENTAL IMPACT PREVIEW
# ============================================================
print("\n=== 6. Environmental Impact Preview ===")
record("Impact", "Impact section ID present", 'id="impact"' in html)
record("Impact", "Illustrative / demo data disclosure banner", "Illustrative Platform Preview" in html)
record("Impact", "Metric 1: Verified missions", "1,420+" in html and "Verified Missions" in html)
record("Impact", "Metric 2: Waste collected", "3,850 kg" in html and "Waste Collected" in html)
record("Impact", "Metric 3: Trees planted", "890+" in html and "Trees Planted" in html)
record("Impact", "Metric 4: Volunteer hours", "2,150 hrs" in html and "Volunteer Hours" in html)

# ============================================================
# 7. FINAL CALL TO ACTION
# ============================================================
print("\n=== 7. Final Call to Action ===")
record("CTA", "Exact Headline present", "Your Actions Can Make a Difference." in html)
record("CTA", "Exact Description present", "Start small. Take action. Create measurable change." in html)
record("CTA", "Exact Button text present", "Join EcoQuest" in html)

# ============================================================
# 8. FOOTER
# ============================================================
print("\n=== 8. Footer ===")
record("Footer", "Footer landmark present", "<footer" in html and 'role="contentinfo"' in html)
record("Footer", "EcoQuest branding in footer", "EcoQuest" in html)
record("Footer", "Platform description in footer", "Learn. Act. Verify. Change the Planet." in html)
record("Footer", "Platform navigation links", "Platform" in html)
record("Footer", "Contact section present", "contact@ecoquest.org" in html)
record("Footer", "Copyright information present", "All rights reserved" in html)

# ============================================================
# 9. BUTTON & LINK DESTINATIONS (ALL HTTP 200)
# ============================================================
print("\n=== 9. Route & Link Destinations ===")
routes_to_test = [
    ("/", (200,), "Home"),
    ("/auth/register", (200,), "Start Your Eco Journey / Join EcoQuest"),
    ("/missions/", (200,), "Explore Missions / Featured Missions"),
    ("/learning/", (200,), "Learn"),
    ("/leaderboard/", (200,), "Leaderboard"),
    ("/auth/login", (200,), "Login"),
    ("/dashboard/", (200, 302), "Dashboard (protected)"),
]

for route, expected_statuses, label in routes_to_test:
    r = client.get(route)
    record("Routes", f"{label} ({route}) reachable", r.status_code in expected_statuses)

# ============================================================
# 10. STATIC ASSETS SERVING
# ============================================================
print("\n=== 10. Static Assets Serving ===")
static_assets = [
    ("/static/css/style.css", "CSS base design system"),
    ("/static/css/landing.css", "CSS landing page stylesheet"),
    ("/static/js/app.js", "Vanilla JavaScript controller"),
    ("/static/images/mission-cleanup.svg", "Clean a Public Area SVG image"),
    ("/static/images/mission-tree.svg", "Plant a Native Tree SVG image"),
    ("/static/images/mission-recycling.svg", "Collect Recyclable Waste SVG image"),
]

for asset_url, label in static_assets:
    r = client.get(asset_url)
    record("Assets", f"GET {asset_url} ({label}) -> 200", r.status_code == 200)

# ============================================================
# 11. RESPONSIVENESS & ACCESSIBILITY
# ============================================================
print("\n=== 11. Responsiveness & Accessibility ===")
with open(os.path.join(BASE_DIR, "static", "css", "landing.css"), "r", encoding="utf-8") as f:
    landing_css = f.read()

record("Responsive", "max-width: 1024px tablet breakpoint exists", "max-width: 1024px" in landing_css)
record("Responsive", "max-width: 768px mobile breakpoint exists", "max-width: 768px" in landing_css)
record("Responsive", "max-width: 480px small mobile breakpoint exists", "max-width: 480px" in landing_css)
record("Accessibility", "Landmarks: <nav>, <main>, <footer>, <section>",
       "<nav" in html and "<main" in html and "<footer" in html and "<section" in html)
record("Accessibility", "Images have descriptive alt tags",
       'alt="Illustration of volunteers cleaning up a public park"' in html and
       'alt="Illustration of a native sapling being planted and watered"' in html and
       'alt="Illustration of sorted recyclable bins and containers"' in html)

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print(f"  LANDING PAGE VERIFICATION TOTAL: {PASS + FAIL}")
print(f"  PASSED: {PASS}  |  FAILED: {FAIL}")
print("=" * 60)

if FAIL > 0:
    print("\nFailed checks:")
    for r in RESULTS:
        if not r["passed"]:
            print(f"  [FAIL] ({r['section']}) {r['name']} — {r['detail']}")

if __name__ == "__main__":
    sys.exit(0 if FAIL == 0 else 1)
