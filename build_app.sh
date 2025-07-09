#!/bin/bash
# Build script for Type Proofing app with proper entitlements

echo "Building Type Proofing app..."

# Clean previous builds
rm -rf build/ dist/

# Build the app with py2app
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 setup.py py2app --arch=universal2

# Check if build was successful
if [ ! -d "dist/TypeProofing.app" ]; then
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
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
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

export APP="TypeProofing.app"
export IDENTITY="Developer ID Application: JOSE MIGUEL SOLE BRUNING (8YVTA46P66)"
export OPTIONS="--verbose --options runtime --timestamp "
export FRAMEWORK="dist/${APP}/Contents/Frameworks/Python.framework/Versions/3.13/Python"
export LOGFILE="build.log"

export ZIP_NAME="python313.zip"
export ORIGINAL_ZIP_DIR="dist/${APP}/Contents/Resources/lib"
export PYTHON_ZIP="${ORIGINAL_ZIP_DIR}/${ZIP_NAME}"
export TEMP_DIR="/tmp"
export UNZIP_DIR="python313"
echo "Get copy of unsigned zip file"
cp -p ${PYTHON_ZIP} ${TEMP_DIR}
echo "Unzip it"
/usr/bin/ditto -x -k "${TEMP_DIR}/${ZIP_NAME}" "${TEMP_DIR}/${UNZIP_DIR}"

find "${TEMP_DIR}/${UNZIP_DIR}/PIL/.dylibs" -iname '*.dylib' |
    while read libfile; do
        codesign --force --sign "Developer ID Application: JOSE MIGUEL SOLE BRUNING (8YVTA46P66)" --verbose --options runtime --timestamp "${libfile}" ;
    done;

echo "Remove old temp copy zip file" rm -vrf "${TEMP_DIR}/${ZIP_NAME}"
echo "recreate zip file"
/usr/bin/ditto -c -k "${TEMP_DIR}/${UNZIP_DIR}" "${TEMP_DIR}/${ZIP_NAME}"
echo "Move signed zip back"
cp -p "${TEMP_DIR}/${ZIP_NAME}" ${ORIGINAL_ZIP_DIR}

codesign --force --sign "Developer ID Application: JOSE MIGUEL SOLE BRUNING (8YVTA46P66)" --verbose --options runtime --timestamp --entitlements temp_entitlements.plist ${FRAMEWORK}

echo "Sign libraries"
find "dist/${APP}" -iname '*.so' -or -iname '*.dylib' |
    while read libfile; do
        codesign --force --sign "Developer ID Application: JOSE MIGUEL SOLE BRUNING (8YVTA46P66)" --verbose --options runtime --timestamp "${libfile}" ;
    done;

codesign --force --sign "Developer ID Application: JOSE MIGUEL SOLE BRUNING (8YVTA46P66)" --verbose --options runtime --timestamp "dist/${APP}/Contents/Resources/lib/python3.13/drawBot/context/tools/ffmpeg"
codesign --force --sign "Developer ID Application: JOSE MIGUEL SOLE BRUNING (8YVTA46P66)" --verbose --options runtime --timestamp "dist/${APP}/Contents/Resources/lib/python3.13/drawBot/context/tools/potrace"
codesign --force --sign "Developer ID Application: JOSE MIGUEL SOLE BRUNING (8YVTA46P66)" --verbose --options runtime --timestamp "dist/${APP}/Contents/Resources/lib/python3.13/drawBot/context/tools/gifsicle"
codesign --force --sign "Developer ID Application: JOSE MIGUEL SOLE BRUNING (8YVTA46P66)" --verbose --options runtime --timestamp "dist/${APP}/Contents/Resources/lib/python3.13/drawBot/context/tools/mkbitmap"

codesign --force --sign "Developer ID Application: JOSE MIGUEL SOLE BRUNING (8YVTA46P66)" --verbose --options runtime --timestamp "dist/${APP}/Contents/MacOS/python"
codesign --force --sign "Developer ID Application: JOSE MIGUEL SOLE BRUNING (8YVTA46P66)" --verbose --options runtime --timestamp "dist/${APP}/Contents/MacOS/TypeProofing"

codesign --force --sign "Developer ID Application: JOSE MIGUEL SOLE BRUNING (8YVTA46P66)" --verbose --options runtime --timestamp --entitlements temp_entitlements.plist "dist/${APP}"

# codesign --verify --verbose=4 dist/TypeProofing.app

# xcrun notarytool submit "dist/TypeProofing.zip" \
#   --apple-id "me@jmsole.cl" \
#   --team-id "8YVTA46P66" \
#   --password "rdid-ycrs-gngl-emhs" \
#   --wait

# xcrun notarytool log --apple-id me@jmsole.cl --team-id 8YVTA46P66 --password rdid-ycrs-gngl-emhs a2ed01ef-0ac5-4003-be05-71595651e56e

# xcrun stapler staple dist/TypeProofing.app

# Check if codesign was successful
if [ $? -eq 0 ]; then
    echo "Entitlements applied successfully!"
else
    echo "Warning: Could not apply entitlements. The app may still work but might have limited file access."
fi

# Clean up temporary file
rm -f temp_entitlements.plist

echo "Build complete! Your app is in: dist/Type Proofing.app"
