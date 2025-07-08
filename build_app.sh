#!/bin/bash
# Build script for Type Proofing app with proper entitlements

echo "Building Type Proofing app..."

# Clean previous builds
rm -rf build/ dist/

# Build the app with py2app
python setup.py py2app --arch=universal2

# Check if build was successful
if [ ! -d "dist/Type Proofing.app" ]; then
    echo "Error: App build failed!"
    exit 1
fi

echo "App built successfully!"

# Apply entitlements to disable sandboxing and allow iCloud Drive access
echo "Applying entitlements..."

# Create a temporary entitlements file for codesign
cat > temp_entitlements.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Disable app sandboxing to allow full file system access -->
    <key>com.apple.security.app-sandbox</key>
    <false/>
    
    <!-- Allow access to user-selected files and directories -->
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
    
    <!-- Allow access to various folders -->
    <key>com.apple.security.files.downloads.read-write</key>
    <true/>
    
    <key>com.apple.security.files.documents.read-write</key>
    <true/>
    
    <key>com.apple.security.files.pictures.read-write</key>
    <true/>
    
    <!-- Allow network access -->
    <key>com.apple.security.network.client</key>
    <true/>
    
    <!-- Allow access to bookmark data -->
    <key>com.apple.security.files.bookmarks.app-scope</key>
    <true/>
</dict>
</plist>
EOF

# Apply entitlements without code signing (for development/personal use)
echo "Applying entitlements to the app bundle..."
codesign --force --sign - --entitlements temp_entitlements.plist "dist/Type Proofing.app"

# Check if codesign was successful
if [ $? -eq 0 ]; then
    echo "Entitlements applied successfully!"
else
    echo "Warning: Could not apply entitlements. The app may still work but might have limited file access."
fi

# Clean up temporary file
rm -f temp_entitlements.plist

echo "Build complete! Your app is in: dist/Type Proofing.app"
