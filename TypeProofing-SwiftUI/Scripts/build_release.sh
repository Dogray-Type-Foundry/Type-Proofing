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
#   1. NativeLib/libtpnative.a built for the target architecture
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

# ── 0. Verify NativeLib exists ────────────────────────────────────────
if [ ! -f "${PROJECT_DIR}/NativeLib/libtpnative.a" ]; then
    echo "Error: NativeLib/libtpnative.a not found."
    echo "Build the Rust native library first."
    exit 1
fi

# ── 1. Regenerate Xcode project ──────────────────────────────────────
echo "Regenerating Xcode project…"
cd "${PROJECT_DIR}"
xcodegen generate --spec project.yml 2>/dev/null || {
    echo "Error: xcodegen failed. Install with: brew install xcodegen"
    exit 1
}

# ── 2. Build Release configuration ───────────────────────────────────
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

# ── 3. Copy to dist/ ─────────────────────────────────────────────────
mkdir -p "${DIST_DIR}"
rm -rf "${DIST_DIR}/${APP}"
cp -R "${BUILD_APP}" "${DIST_DIR}/${APP}"
echo "✓ Copied to dist/${APP}"

# ── 4. Copy Assets.car for macOS 26+ icon support ────────────────────
if [ -f "${REPO_ROOT}/Assets.car" ]; then
    cp "${REPO_ROOT}/Assets.car" "${DIST_DIR}/${APP}/Contents/Resources/Assets.car"
    echo "✓ Assets.car copied"
fi

# ── 5. Code signing ──────────────────────────────────────────────────
echo "Signing…"

SIGN_OPTS=(--force --sign "${CODESIGN_ID}" --options runtime --timestamp)

# Sign the main executable
echo "  Signing main executable…"
codesign "${SIGN_OPTS[@]}" --entitlements "${ENTITLEMENTS}" "${DIST_DIR}/${APP}/Contents/MacOS/${APP_NAME}"

# Sign the app bundle
echo "  Signing app bundle…"
codesign "${SIGN_OPTS[@]}" --entitlements "${ENTITLEMENTS}" "${DIST_DIR}/${APP}"

echo "✓ Signing complete"

# ── 6. Verify ────────────────────────────────────────────────────────
echo "Verifying…"
codesign --verify --deep --strict "${DIST_DIR}/${APP}" 2>&1 || {
    echo "Warning: Signature verification issues (expected with ad-hoc)"
}

# ── 7. Create DMG ────────────────────────────────────────────────────
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

# ── 8. Notarize (optional) ───────────────────────────────────────────
NOTARY_PROFILE="${NOTARY_PROFILE:-TypeProofing}"

if [ "${NOTARIZE:-0}" = "1" ] && [ "${CODESIGN_ID}" != "-" ]; then
    echo "Submitting for notarization…"

    NOTARY_RC=0
    NOTARY_AUTH=""
    NOTARY_OUTPUT="$(mktemp "${TMPDIR:-/tmp}/typeproofing-notary.XXXXXX")"
    if xcrun notarytool history --keychain-profile "${NOTARY_PROFILE}" >/dev/null 2>&1; then
        echo "  Using keychain profile: ${NOTARY_PROFILE}"
        NOTARY_AUTH="keychain"
        set +e
        xcrun notarytool submit "${DMG_PATH}" \
            --keychain-profile "${NOTARY_PROFILE}" \
            --wait 2>&1 | tee "${NOTARY_OUTPUT}"
        NOTARY_RC=${PIPESTATUS[0]}
        set -e
    elif [ -n "${APPLE_ID:-}" ] && [ -n "${TEAM_ID:-}" ] && [ -n "${NOTARIZE_PASSWORD:-}" ]; then
        echo "  Using environment variable credentials"
        NOTARY_AUTH="env"
        set +e
        xcrun notarytool submit "${DMG_PATH}" \
            --apple-id "${APPLE_ID}" \
            --team-id "${TEAM_ID}" \
            --password "${NOTARIZE_PASSWORD}" \
            --wait 2>&1 | tee "${NOTARY_OUTPUT}"
        NOTARY_RC=${PIPESTATUS[0]}
        set -e
    else
        echo "Error: No notarization credentials found."
        echo "  Either store a keychain profile:"
        echo "    xcrun notarytool store-credentials \"${NOTARY_PROFILE}\" \\"
        echo "      --apple-id <email> --team-id <team> --password <app-specific-pw>"
        echo "  Or set APPLE_ID, TEAM_ID, and NOTARIZE_PASSWORD environment variables."
        exit 1
    fi

    SUBMISSION_ID="$(awk '/^[[:space:]]*id: / { print $2; exit }' "${NOTARY_OUTPUT}")"
    NOTARY_STATUS="$(awk '/^[[:space:]]*status: / { print $2; exit }' "${NOTARY_OUTPUT}")"

    if [ "${NOTARY_RC}" -ne 0 ] || [ "${NOTARY_STATUS}" != "Accepted" ]; then
        echo ""
        echo "✗ Notarization failed."
        echo "  Exit code: ${NOTARY_RC}"
        echo "  Status: ${NOTARY_STATUS:-unknown}"
        if [ -n "${SUBMISSION_ID}" ]; then
            echo "  Submission ID: ${SUBMISSION_ID}"
        fi
        echo "  Fetch the detailed log with:"
        if [ "${NOTARY_AUTH}" = "keychain" ] && [ -n "${SUBMISSION_ID}" ]; then
            echo "    xcrun notarytool log ${SUBMISSION_ID} --keychain-profile \"${NOTARY_PROFILE}\""
        elif [ "${NOTARY_AUTH}" = "env" ] && [ -n "${SUBMISSION_ID}" ]; then
            echo "    xcrun notarytool log ${SUBMISSION_ID} --apple-id \"\${APPLE_ID}\" --team-id \"\${TEAM_ID}\" --password \"\${NOTARIZE_PASSWORD}\""
        else
            echo "    xcrun notarytool log <submission-id> --keychain-profile \"${NOTARY_PROFILE}\""
        fi
        exit 1
    fi

    echo "Stapling notarization ticket…"
    xcrun stapler staple "${DMG_PATH}"
    echo "✓ Notarization complete"
fi

# ── Done ─────────────────────────────────────────────────────────────
echo ""
echo "=== Build complete ==="
echo "  App: ${DIST_DIR}/${APP}"
echo "  DMG: ${DMG_PATH}"
APP_SIZE=$(du -sh "${DIST_DIR}/${APP}" | cut -f1)
echo "  App size: ${APP_SIZE}"
if [ -f "${DMG_PATH}" ]; then
    DMG_SIZE=$(du -sh "${DMG_PATH}" | cut -f1)
    echo "  DMG size: ${DMG_SIZE}"
fi
