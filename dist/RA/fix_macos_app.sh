#!/bin/bash
# Fix for wxPython symbol issues on macOS
# This script should be run after installation if you encounter issues

APP_PATH="$(cd "$(dirname "$0")" && pwd)"
echo "Fixing wxPython compatibility issues in: $APP_PATH"

# Fix library paths if needed
install_name_tool -change @loader_path/libwx_baseu-3.1.dylib @executable_path/libwx_baseu-3.1.dylib "$APP_PATH/wx/_core.so" 2>/dev/null || true
install_name_tool -change @loader_path/libwx_osx_cocoau-3.1.dylib @executable_path/libwx_osx_cocoau-3.1.dylib "$APP_PATH/wx/_core.so" 2>/dev/null || true

echo "Fix completed. Try running the app again."
