#!/usr/bin/env python
# macOS launcher to ensure proper environment for wxPython
import os
import sys
import subprocess

if __name__ == "__main__":
    # Get the directory containing this script
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Add this directory to Python path
    sys.path.insert(0, app_dir)
    
    # Set environment variables for macOS GUI compatibility
    os.environ['PYTHONHOME'] = app_dir
    os.environ['DYLD_LIBRARY_PATH'] = os.path.join(app_dir, 'lib')
    os.environ['DYLD_FRAMEWORK_PATH'] = app_dir
    
    # Import and run the main module
    import main
