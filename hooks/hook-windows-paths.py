
# Windows specific compatibility hook
import os
import sys
import ctypes
import platform

if getattr(sys, 'frozen', False) and sys.platform == 'win32':
    # We're running as a Windows executable
    app_path = os.path.dirname(sys.executable)
    
    # Set DPI awareness to improve rendering on Windows
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Process system DPI aware
    except:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # Fallback for older Windows
        except:
            pass  # Ignore if both methods fail
    
    # Set environment variables
    os.environ['RA_APP_PATH'] = app_path
    
    # Print Windows-specific info
    print(f"Windows Version: {platform.win32_ver()[0]}")
    print(f"App Path: {app_path}")
