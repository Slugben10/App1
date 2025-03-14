
# macOS specific hook for wxPython framework
import os
import sys

# Set environment variable for wxPython to work correctly
os.environ['PYTHONHOME'] = sys.prefix

# For macOS, add this to ensure we use the correct Python framework
if sys.platform == 'darwin':
    os.environ['PYTHONEXECUTABLE'] = sys.executable
    os.environ['PYTHONFRAMEWORK'] = '/Library/Frameworks/Python.framework'
