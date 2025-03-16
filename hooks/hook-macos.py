
# macOS-specific hook for Framework Python issues
import os
import sys

# This will run when the frozen app starts
if sys.platform == 'darwin':
    os.environ['PYTHONHOME'] = os.path.dirname(sys.executable)
    # Ensure frameworks can be found
    os.environ['DYLD_LIBRARY_PATH'] = os.path.join(os.path.dirname(sys.executable), 'lib')
    os.environ['DYLD_FRAMEWORK_PATH'] = os.path.dirname(sys.executable)
