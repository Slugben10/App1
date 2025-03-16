
# Special macOS hook for wxPython app
import os
import sys

# Force macOS to use the framework Python when running our app
if sys.platform == 'darwin':
    # This ensures the app runs with the proper Python framework
    os.environ['PYTHONHOME'] = sys.prefix
    
    # Add an environment variable so the app can find its resources
    if getattr(sys, 'frozen', False):
        # Running as a bundled executable
        APP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(sys.executable))))
        os.environ['RA_APP_PATH'] = APP_PATH
        os.environ['DYLD_LIBRARY_PATH'] = os.path.join(APP_PATH, 'Frameworks')
