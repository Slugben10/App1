
# General application hook
import os
import sys

# Ensure we can find the app's resources
if getattr(sys, 'frozen', False):
    # Running as a bundled executable
    APP_PATH = os.path.dirname(sys.executable)
    os.environ['RA_APP_PATH'] = APP_PATH
