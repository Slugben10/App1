#!/bin/bash
# Fix for wxPython symbol issues on macOS
# This script should be run after installation if you encounter issues

APP_PATH="$(cd "$(dirname "$0")" && pwd)"
echo "Fixing wxPython compatibility issues in: $APP_PATH"

# Fix library paths if needed
install_name_tool -change @loader_path/libwx_baseu-3.1.dylib @executable_path/libwx_baseu-3.1.dylib "$APP_PATH/wx/_core.so" 2>/dev/null || true
install_name_tool -change @loader_path/libwx_osx_cocoau-3.1.dylib @executable_path/libwx_osx_cocoau-3.1.dylib "$APP_PATH/wx/_core.so" 2>/dev/null || true

# Create symbolic links to ensure files can be found
BUNDLE_DIR="$(dirname "$(dirname "$APP_PATH")")"
echo "Creating symbolic links in bundle directory: $BUNDLE_DIR"

# Link .env and config.json if they exist
[ -f "$APP_PATH/.env" ] && ln -sf "$APP_PATH/.env" "$BUNDLE_DIR/.env" 2>/dev/null || true
[ -f "$APP_PATH/config.json" ] && ln -sf "$APP_PATH/config.json" "$BUNDLE_DIR/config.json" 2>/dev/null || true

echo "Fix completed. Try running the app again."
