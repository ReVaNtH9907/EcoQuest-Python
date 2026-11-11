"""
Vercel Serverless Function Handler for EcoQuest.
Routes HTTP requests to the Flask application instance.
"""

import os
import sys

# Ensure application root directory is on the Python module search path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app

# Instantiate Flask application for Vercel WSGI
app = create_app()
