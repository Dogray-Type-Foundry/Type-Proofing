#!/bin/bash
# build_release.sh — Build, sign, and package the SwiftUI TypeProofing app
#
# Usage:
#   bash TypeProofing-SwiftUI/Scripts/build_release.sh
#
# Environment:
#   CODESIGN_ID — Developer ID Application identity (optional; ad-hoc if unset)
#   NOTARIZE    — set to "1" to notarize after building
#
# Notarization credentials (pick ONE method):
#   Method A — keychain profile (recommended, one-time setup):
#     NOTARY_PROFILE — keychain profile name (default: "TypeProofing")
#     Setup:  xcrun notarytool store-credentials "TypeProofing" \
#               --apple-id <email> --team-id <team> --password <app-specific-pw>
#
#   Method B — environment variables (legacy / CI):
#     APPLE_ID, TEAM_ID, NOTARIZE_PASSWORD
#
# Prerequisites:
#   1. Run Scripts/bundle_python_packages.sh once to populate python-packages/
#   2. Xcode 16+ with Swift 5.9+ toolchain
#   3. xcodegen installed (brew install xcodegen)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$PROJECT_DIR")"
DIST_DIR="${REPO_ROOT}/dist"

APP_NAME="TypeProofing"
APP="${APP_NAME}.app"
ENTITLEMENTS="${PROJECT_DIR}/TypeProofing/TypeProofing.entitlements"

# Use ad-hoc signing if no identity provided
CODESIGN_ID="${CODESIGN_ID:--}"

echo "=== Type Proofing SwiftUI — Release Build ==="
echo "  Project:    ${PROJECT_DIR}"
echo "  Signing ID: ${CODESIGN_ID}"
echo ""

# ── 0. Ensure python-packages exists ───────────────────────────────────
if [ ! -d "${PROJECT_DIR}/python-packages" ]; then
    echo "Error: python-packages/ not found."
    echo "Run: bash TypeProofing-SwiftUI/Scripts/bundle_python_packages.sh"
    exit 1
fi

# ── 1. Regenerate Xcode project if needed ──────────────────────────────
echo "Regenerating Xcode project…"
cd "${PROJECT_DIR}"
xcodegen generate --spec project.yml 2>/dev/null || {
    echo "Error: xcodegen failed. Install with: brew install xcodegen"
    exit 1
}

# ── 2. Build Release configuration ────────────────────────────────────
echo "Building Release…"
xcodebuild -project "${APP_NAME}.xcodeproj" \
    -scheme "${APP_NAME}" \
    -configuration Release \
    -derivedDataPath "${PROJECT_DIR}/build-release" \
    CODE_SIGN_IDENTITY="-" \
    CODE_SIGNING_ALLOWED=NO \
    clean build 2>&1 | tail -5

BUILD_APP="${PROJECT_DIR}/build-release/Build/Products/Release/${APP}"
if [ ! -d "${BUILD_APP}" ]; then
    echo "Error: Build failed — ${APP} not found"
    exit 1
fi
echo "✓ Build succeeded"

# ── 3. Copy to dist/ ──────────────────────────────────────────────────
mkdir -p "${DIST_DIR}"
rm -rf "${DIST_DIR}/${APP}"
cp -R "${BUILD_APP}" "${DIST_DIR}/${APP}"
echo "✓ Copied to dist/${APP}"

# ── 4. Copy Assets.car for macOS 26+ icon support ─────────────────────
if [ -f "${REPO_ROOT}/Assets.car" ]; then
    cp "${REPO_ROOT}/Assets.car" "${DIST_DIR}/${APP}/Contents/Resources/Assets.car"
    echo "✓ Assets.car copied"
fi

# ── 4b. Fix Python.framework install names ────────────────────────────
# The system Python.framework uses an absolute install_name. We must rewrite
# it to @rpath so the app loads its embedded copy instead of the system one.
EMBEDDED_PYTHON="${DIST_DIR}/${APP}/Contents/Frameworks/Python.framework/Versions/3.13/Python"
OLD_ID="/Library/Frameworks/Python.framework/Versions/3.13/Python"
NEW_ID="@rpath/Python.framework/Versions/3.13/Python"
if [ -f "${EMBEDDED_PYTHON}" ]; then
    # Change the dylib's own install_name
    install_name_tool -id "${NEW_ID}" "${EMBEDDED_PYTHON}"
    # Change the main binary's reference to Python
    install_name_tool -change "${OLD_ID}" "${NEW_ID}" "${DIST_DIR}/${APP}/Contents/MacOS/${APP_NAME}"
    echo "✓ Python.framework install_name fixed to @rpath"
fi

# ── 5. Code signing (inside out) ──────────────────────────────────────
echo "Signing…"

SIGN_OPTS=(--force --sign "${CODESIGN_ID}" --options runtime --timestamp)

# 5a. Remove static stubs and dev-only files from Tcl/Tk (not needed at runtime, breaks signing)
find "${DIST_DIR}/${APP}/Contents/Frameworks" -name '*.a' -delete 2>/dev/null || true
find "${DIST_DIR}/${APP}/Contents/Frameworks" -name '*Config.sh' -delete 2>/dev/null || true
find "${DIST_DIR}/${APP}/Contents/Frameworks" -name 'pkgconfig' -type d -exec rm -rf {} + 2>/dev/null || true

# 5a2. Clean Python.framework: remove stale versions and dev-only directories
PY_FW_DIR="${DIST_DIR}/${APP}/Contents/Frameworks/Python.framework"
PY_VER_DIR="${PY_FW_DIR}/Versions/3.13"
# Remove any non-Current framework versions (e.g. 3.10)
for ver_dir in "${PY_FW_DIR}"/Versions/*/; do
    ver_name="$(basename "$ver_dir")"
    if [ "$ver_name" != "3.13" ] && [ "$ver_name" != "Current" ]; then
        rm -rf "$ver_dir"
        echo "  Removed stale framework version: ${ver_name}"
    fi
done
# Remove development-only directories from the active version (keep lib — it has the stdlib)
for dev_dir in bin etc include share; do
    rm -rf "${PY_VER_DIR}/${dev_dir}" 2>/dev/null || true
done

# 5a3. Slim Python.framework — remove large unused components
# The app loads packages from Resources/python-lib (curated), so the full
# site-packages inside the framework is dead weight.
PY_LIB="${PY_VER_DIR}/lib/python3.13"
BEFORE_SIZE=$(du -sm "${PY_FW_DIR}" | cut -f1)

# Remove entire site-packages (all needed packages are in Resources/python-lib)
rm -rf "${PY_LIB}/site-packages"

# Remove CPython test suite (~206 MB)
rm -rf "${PY_LIB}/test"

# Remove stdlib modules not needed at runtime
for mod in idlelib ensurepip tkinter turtledemo turtle.py pydoc_data pydoc.py; do
    rm -rf "${PY_LIB}/${mod}" 2>/dev/null || true
done

# Remove config-* directories (C extension build configs containing python.o
# which has an invalid/weak signature that blocks notarization)
rm -rf "${PY_LIB}"/config-* 2>/dev/null || true

# Remove all __pycache__ directories (regenerated on first import)
find "${PY_LIB}" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Remove .pyc files outside __pycache__ if any
find "${PY_LIB}" -name "*.pyc" -delete 2>/dev/null || true

# Remove Tcl/Tk frameworks (app uses Vanilla/AppKit, not tkinter)
rm -rf "${PY_VER_DIR}/Frameworks/Tcl.framework" "${PY_VER_DIR}/Frameworks/Tk.framework" 2>/dev/null || true
rmdir "${PY_VER_DIR}/Frameworks" 2>/dev/null || true

# Remove test and unused C extensions from lib-dynload
for ext in _test*.so _tkinter*.so _sqlite3*.so _curses*.so _dbm*.so _gdbm*.so; do
    rm -f "${PY_LIB}/lib-dynload/${ext}" 2>/dev/null || true
done

AFTER_SIZE=$(du -sm "${PY_FW_DIR}" | cut -f1)
echo "  Python.framework slimmed: ${BEFORE_SIZE}MB → ${AFTER_SIZE}MB (saved $((BEFORE_SIZE - AFTER_SIZE))MB)"

# 5a4. Slim python-lib — remove DrawBot tools not needed for PDF-only output
PYTHON_LIB_DIR="${DIST_DIR}/${APP}/Contents/Resources/python-lib"
DRAWBOT_TOOLS="${PYTHON_LIB_DIR}/drawBot/context/tools"
for tool in ffmpeg gifsicle; do
    rm -f "${DRAWBOT_TOOLS}/${tool}" 2>/dev/null || true
done

# Remove PIL/Pillow — only used by DrawBot's imageObjectContext (bitmap ops),
# not needed for PDF generation
rm -rf "${PYTHON_LIB_DIR}/PIL" 2>/dev/null || true

# Strip __pycache__ from python-lib (regenerated on first import)
find "${PYTHON_LIB_DIR}" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# 5b. Sign all native extensions (.so, .dylib) in python-lib/ and Frameworks/
echo "  Signing native extensions…"
find "${DIST_DIR}/${APP}/Contents/Resources/python-lib" \
    "${DIST_DIR}/${APP}/Contents/Frameworks/Python.framework/Versions/3.13/lib" \
    \( -name '*.so' -o -name '*.dylib' \) -print0 |
    while IFS= read -r -d '' libfile; do
        codesign "${SIGN_OPTS[@]}" "${libfile}" 2>/dev/null || true
    done

# 5b. Sign DrawBot tools
echo "  Signing DrawBot tools…"
TOOLS_DIR="${DIST_DIR}/${APP}/Contents/Resources/python-lib/drawBot/context/tools"
for tool in ffmpeg potrace gifsicle mkbitmap; do
    if [ -f "${TOOLS_DIR}/${tool}" ]; then
        codesign "${SIGN_OPTS[@]}" "${TOOLS_DIR}/${tool}" 2>/dev/null || true
    fi
done

# 5d. Sign Tcl & Tk frameworks inside Python.framework
echo "  Signing Tcl/Tk frameworks…"
PY_FRAMEWORKS="${DIST_DIR}/${APP}/Contents/Frameworks/Python.framework/Versions/3.13/Frameworks"
for fw in Tcl Tk; do
    if [ -d "${PY_FRAMEWORKS}/${fw}.framework" ]; then
        codesign "${SIGN_OPTS[@]}" "${PY_FRAMEWORKS}/${fw}.framework" 2>/dev/null || true
    fi
done

# 5f. Sign Python.framework
echo "  Signing Python.framework…"
PYTHON_FW="${DIST_DIR}/${APP}/Contents/Frameworks/Python.framework/Versions/3.13/Python"
if [ -f "${PYTHON_FW}" ]; then
    codesign "${SIGN_OPTS[@]}" --entitlements "${ENTITLEMENTS}" "${PYTHON_FW}"
fi

# 5g. Sign the main executable
echo "  Signing main executable…"
codesign "${SIGN_OPTS[@]}" "${DIST_DIR}/${APP}/Contents/MacOS/${APP_NAME}"

# 5h. Sign the app bundle
echo "  Signing app bundle…"
codesign "${SIGN_OPTS[@]}" --entitlements "${ENTITLEMENTS}" "${DIST_DIR}/${APP}"

echo "✓ Signing complete"

# ── 6. Verify ─────────────────────────────────────────────────────────
echo "Verifying…"
codesign --verify --deep --strict "${DIST_DIR}/${APP}" 2>&1 || {
    echo "Warning: Signature verification issues (expected with ad-hoc)"
}

# ── 7. Create DMG ─────────────────────────────────────────────────────
echo "Creating DMG…"
DMG_PATH="${DIST_DIR}/${APP_NAME}.dmg"
rm -f "${DMG_PATH}"
hdiutil create -volname "Type Proofing" \
    -srcfolder "${DIST_DIR}/${APP}" \
    -ov -format UDZO \
    "${DMG_PATH}" 2>/dev/null

if [ "${CODESIGN_ID}" != "-" ]; then
    codesign --force --sign "${CODESIGN_ID}" --options runtime --timestamp "${DMG_PATH}"
fi

echo "✓ DMG created: ${DMG_PATH}"

# ── 8. Notarize (optional) ────────────────────────────────────────────
NOTARY_PROFILE="${NOTARY_PROFILE:-TypeProofing}"

if [ "${NOTARIZE:-0}" = "1" ] && [ "${CODESIGN_ID}" != "-" ]; then
    echo "Submitting for notarization…"

    NOTARY_RC=0
    # Prefer keychain profile; fall back to env-var credentials
    if xcrun notarytool history --keychain-profile "${NOTARY_PROFILE}" >/dev/null 2>&1; then
        echo "  Using keychain profile: ${NOTARY_PROFILE}"
        xcrun notarytool submit "${DMG_PATH}" \
            --keychain-profile "${NOTARY_PROFILE}" \
            --wait || NOTARY_RC=$?
    elif [ -n "${APPLE_ID:-}" ] && [ -n "${TEAM_ID:-}" ] && [ -n "${NOTARIZE_PASSWORD:-}" ]; then
        echo "  Using environment variable credentials"
        xcrun notarytool submit "${DMG_PATH}" \
            --apple-id "${APPLE_ID}" \
            --team-id "${TEAM_ID}" \
            --password "${NOTARIZE_PASSWORD}" \
            --wait || NOTARY_RC=$?
    else
        echo "Error: No notarization credentials found."
        echo "  Either store a keychain profile:"
        echo "    xcrun notarytool store-credentials \"${NOTARY_PROFILE}\" \\"
        echo "      --apple-id <email> --team-id <team> --password <app-specific-pw>"
        echo "  Or set APPLE_ID, TEAM_ID, and NOTARIZE_PASSWORD environment variables."
        exit 1
    fi

    if [ "${NOTARY_RC}" -ne 0 ]; then
        echo ""
        echo "✗ Notarization failed (exit code ${NOTARY_RC})."
        echo "  Fetch the detailed log with:"
        echo "    xcrun notarytool log <submission-id> --keychain-profile \"${NOTARY_PROFILE}\""
        exit 1
    fi

    echo "Stapling notarization ticket…"
    xcrun stapler staple "${DMG_PATH}"
    echo "✓ Notarization complete"
fi

# ── Done ──────────────────────────────────────────────────────────────
echo ""
echo "=== Build complete ==="
echo "  App: ${DIST_DIR}/${APP}"
echo "  DMG: ${DMG_PATH}"
SIZE=$(du -sh "${DIST_DIR}/${APP}" | cut -f1)
echo "  Size: ${SIZE}"
