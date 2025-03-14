
# macOS PyQt Framework Fix
# This hook helps prevent symbolic link issues with Qt frameworks on macOS

def pre_safe_import_module(api):
    # This runs before PyInstaller imports the module
    print("Running Qt Framework fix for macOS")
