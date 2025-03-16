
# Runtime hook for fixing imports
import os
import sys
import importlib.machinery

# Fix sys.path for bundled application
def fix_sys_path():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        
        # Add potential module locations
        paths_to_try = [
            base_dir,
            os.path.join(base_dir, 'lib'),
            os.path.join(base_dir, 'wx'),
        ]
        
        for path in paths_to_try:
            if path not in sys.path and os.path.exists(path):
                sys.path.insert(0, path)

fix_sys_path()
