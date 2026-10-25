#!/usr/bin/env python3
"""
Standalone entry point for Complex Unzip Tool v2
This script is designed to work with PyInstaller builds.
"""

import sys
import os

# Add the package to the path for standalone builds
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    application_path = sys._MEIPASS
else:
    # Running in development
    application_path = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, application_path)

# Import and run the main application
from deepunzip.main import app

if __name__ == "__main__":
    app()
