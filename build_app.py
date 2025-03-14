import os
import shutil
import sys
import json
import subprocess
import importlib.util

# Define the app name for consistent reference
APP_NAME = "RA"

# Ensure base directories exist
os.makedirs("Documents", exist_ok=True)

print(f"Starting build process for {APP_NAME} with wxPython...")

# Check for required dependencies and install if missing
required_packages = ["altgraph", "PyInstaller"]
missing_packages = []

for package in required_packages:
    try:
        importlib.import_module(package)
        print(f"✓ {package} is installed")
    except ImportError:
        missing_packages.append(package)
        print(f"✗ {package} is missing")

if missing_packages:
    print(f"Installing missing dependencies: {', '.join(missing_packages)}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + missing_packages)
        print("Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        print("Please install the following packages manually: " + ", ".join(missing_packages))
        sys.exit(1)

# Import PyInstaller after ensuring it's installed
import PyInstaller.__main__ as pyinstaller_main

# Try to import wx to get its path
try:
    import wx
    wx_path = os.path.dirname(wx.__file__)
    print(f"Found wxPython at: {wx_path}")
    wx_version = wx.__version__
    print(f"wxPython version: {wx_version}")
    HAS_WX = True
except ImportError:
    print("Warning: wxPython not found. Trying to continue anyway...")
    wx_path = ""
    HAS_WX = False

# Create a default config.json if it doesn't exist
if not os.path.exists("config.json"):
    print("Creating default config.json...")
    default_config = {
        "models": {
            "openai": {
                "name": "OpenAI GPT-4",
                "api_key_env": "OPENAI_API_KEY",
                "model_name": "gpt-4"
            },
            "anthropic": {
                "name": "Anthropic Claude",
                "api_key_env": "ANTHROPIC_API_KEY",
                "model_name": "claude-3-opus-20240229"
            },
            "gemini": {
                "name": "Google Gemini",
                "api_key_env": "GOOGLE_API_KEY",
                "model_name": "gemini-pro"
            }
        },
        "default_model": "openai",
        "max_tokens": 8000,
        "system_prompt": "You are a helpful AI research assistant. Your goal is to help researchers write new papers or expand work-in-progress papers based on the provided documents and instructions."
    }
    
    with open("config.json", "w") as f:
        json.dump(default_config, f, indent=2)
    print("Default config.json created successfully")

# Create runtime hooks directory if it doesn't exist
if not os.path.exists("hooks"):
    os.makedirs("hooks", exist_ok=True)

# Create wxPython hook for compatibility - simpler version to avoid altgraph issues
wx_hook_path = os.path.join("hooks", "hook-wx.py")
with open(wx_hook_path, 'w') as f:
    f.write("""
# wxPython hook for better compatibility with PyInstaller
hiddenimports = [
    'wx.lib.scrolledpanel',
    'wx.lib.newevent',
    'wx.lib.colourdb',
    'wx.adv',
    'wx.html',
    'wx.grid',
    'wx.lib.agw',
    'wx._xml',
    'wx._html',
    'wx._adv',
    'wx._core',
    'wx._controls',
]

# Platform-specific imports
import sys
if sys.platform == 'darwin':
    hiddenimports.extend(['wx.lib.osx'])
elif sys.platform == 'win32':
    hiddenimports.extend(['wx.msw'])
""")

# Create general app hook
app_hook_path = os.path.join("hooks", "hook-app.py")
with open(app_hook_path, 'w') as f:
    f.write("""
# General application hook
import os
import sys

# Ensure we can find the app's resources
if getattr(sys, 'frozen', False):
    # Running as a bundled executable
    APP_PATH = os.path.dirname(sys.executable)
    os.environ['RA_APP_PATH'] = APP_PATH
""")

# Define data files to include
data_files = [
    ("config.json", "."),
]

# Add .env file if it exists
if os.path.exists(".env"):
    data_files.append((".env", "."))

# Define hidden imports based on what's used in main.py
hidden_imports = [
    "wx",
    "wx.lib.scrolledpanel",
    "wx.lib.newevent",
    "json",
    "threading",
    "requests",
    "shutil",
    "traceback",
    "dotenv",
    "altgraph",  # Add altgraph explicitly
]

# Try to include optional packages
try:
    import docx
    hidden_imports.append("docx")
except ImportError:
    print("Warning: python-docx not installed. DOCX support will be limited.")

try:
    import pypdf
    hidden_imports.append("pypdf")
except ImportError:
    print("Warning: pypdf not installed. PDF support will be limited.")

# Additional wxPython-specific imports
wxpy_modules = [
    "wx.adv",
    "wx.html",
    "wx.grid",
    "wx.xrc",
    "wx._xml",
    "wx._html",
    "wx._adv",
    "wx._core",
    "wx._controls"
]
hidden_imports.extend(wxpy_modules)

# Base PyInstaller arguments
pyinstaller_args = [
    'main.py',
    '--name=' + APP_NAME,
    '--onedir',
    '--clean',
    '--noconfirm',
]

# Add runtime hooks
pyinstaller_args.append('--runtime-hook=hooks/hook-app.py')

# Add additional hooks directory
pyinstaller_args.append('--additional-hooks-dir=hooks')

# Add hidden imports
for imp in hidden_imports:
    pyinstaller_args.append('--hidden-import=' + imp)

# Add data files
for src, dst in data_files:
    pyinstaller_args.append('--add-data=' + src + os.pathsep + dst)

# Platform specific settings
if sys.platform == 'darwin':  # macOS
    print("Building for macOS...")
    pyinstaller_args.append('--windowed')
    pyinstaller_args.append('--osx-bundle-identifier=com.researchassistant.app')
    
    # Exclude modules that might cause conflicts
    pyinstaller_args.append('--exclude-module=tkinter')
    pyinstaller_args.append('--exclude-module=PySide')
    pyinstaller_args.append('--exclude-module=PyQt5')
    
    # Add icon if available
    if os.path.exists('app_icon.icns'):
        pyinstaller_args.append('--icon=app_icon.icns')
elif sys.platform == 'win32':  # Windows
    print("Building for Windows...")
    
    # Add specific Windows options for wxPython
    pyinstaller_args.append('--hidden-import=wx.msw')
    
    # Add icon if available
    if os.path.exists('app_icon.ico'):
        pyinstaller_args.append('--icon=app_icon.ico')

# Print the PyInstaller command for debugging
print("PyInstaller command:", " ".join(pyinstaller_args))

try:
    # Run PyInstaller
    pyinstaller_main.run(pyinstaller_args)

    # Ensure the Documents directory exists in the output folder
    dist_dir = os.path.join('dist', APP_NAME)
    documents_dir = os.path.join(dist_dir, 'Documents')
    os.makedirs(documents_dir, exist_ok=True)

    # Explicitly copy config.json to the output folder to ensure it's available
    if os.path.exists('config.json'):
        shutil.copy('config.json', dist_dir)
        print(f"Copied config.json to {dist_dir}")

    # Copy .env file to dist folder (if it exists)
    if os.path.exists('.env'):
        shutil.copy('.env', dist_dir)
        print(f"Copied .env to {dist_dir}")

    # For macOS, perform additional compatibility fixes
    if sys.platform == 'darwin':
        app_bundle_path = os.path.join('dist', f"{APP_NAME}.app")
        if os.path.exists(app_bundle_path):
            print(f"Performing additional macOS compatibility fixes for {app_bundle_path}...")
            
            # Create a fixup script to run after installation
            fixup_script = os.path.join(dist_dir, "fix_macos_app.sh")
            with open(fixup_script, 'w') as f:
                f.write("""#!/bin/bash
# Fix for wxPython symbol issues on macOS
# This script should be run after installation if you encounter issues

APP_PATH="$(cd "$(dirname "$0")" && pwd)"
echo "Fixing wxPython compatibility issues in: $APP_PATH"

# Fix library paths if needed
install_name_tool -change @loader_path/libwx_baseu-3.1.dylib @executable_path/libwx_baseu-3.1.dylib "$APP_PATH/wx/_core.so" 2>/dev/null || true
install_name_tool -change @loader_path/libwx_osx_cocoau-3.1.dylib @executable_path/libwx_osx_cocoau-3.1.dylib "$APP_PATH/wx/_core.so" 2>/dev/null || true

echo "Fix completed. Try running the app again."
""")
            
            # Make the script executable
            os.chmod(fixup_script, 0o755)
            print(f"Created macOS compatibility fix script at {fixup_script}")

    print(f"Build complete. Executable is in {dist_dir}")
    print(f"Documents directory created at {documents_dir}")
    
except Exception as e:
    print(f"Error during build process: {e}")
    import traceback
    traceback.print_exc()

print("\nIf you encounter issues with the app:")
print("1. Make sure wxPython is properly installed: pip install -U wxPython")
print("2. Make sure PyInstaller and its dependencies are installed: pip install -U pyinstaller altgraph")
print("3. Try running the app from terminal to see any error output")

if sys.platform == 'darwin':
    print("\nFor macOS-specific wxPython issues:")
    print("1. Try running the fix_macos_app.sh script in the application directory")
    print("2. Ensure you're using a compatible version of wxPython for your macOS version")
    print("3. Consider using PyInstaller 4.10 or newer for better macOS compatibility")