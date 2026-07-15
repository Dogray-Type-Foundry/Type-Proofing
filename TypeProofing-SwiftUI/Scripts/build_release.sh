#!/bin/bash
# build_release.sh — Build, sign, and package the SwiftUI TypeProofing app
#
# Produces two single-architecture app bundles + DMGs (arm64 and x86_64),
# each roughly half the size of a universal build.
#
# Usage:
#   bash TypeProofing-SwiftUI/Scripts/build_release.sh            # both archs
#   bash TypeProofing-SwiftUI/Scripts/build_release.sh arm64      # one arch only
#   bash TypeProofing-SwiftUI/Scripts/build_release.sh x86_64
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
#   1. ProofCore/Binaries/TPNative.xcframework built (native/build_rust.sh)
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
NOTARY_PROFILE="${NOTARY_PROFILE:-TypeProofing}"

echo "=== Type Proofing SwiftUI — Release Build ==="
echo "  Project:    ${PROJECT_DIR}"
echo "  Signing ID: ${CODESIGN_ID}"
echo ""

# ── 0. Build TPNative.xcframework if missing ─────────────────────────
if [ ! -d "${REPO_ROOT}/ProofCore/Binaries/TPNative.xcframework" ]; then
    echo "TPNative.xcframework not found — building from Rust sources…"
    bash "${REPO_ROOT}/native/build_rust.sh"
    echo "✓ TPNative.xcframework built"
fi

# ── 1. Regenerate Xcode project ──────────────────────────────────────
echo "Regenerating Xcode project…"
cd "${PROJECT_DIR}"
xcodegen generate --spec project.yml 2>/dev/null || {
    echo "Error: xcodegen failed. Install with: brew install xcodegen"
    exit 1
}

# ── build_and_package ARCH LABEL ─────────────────────────────────────
# Builds, signs, packages (and optionally notarizes) one architecture.
build_and_package() {
    local ARCH="$1"
    local LABEL="$2"
    local DD="${PROJECT_DIR}/build-release-${ARCH}"
    local OUT_DIR="${DIST_DIR}/${ARCH}"
    local OUT_APP="${OUT_DIR}/${APP}"
    local DMG_PATH="${DIST_DIR}/${APP_NAME}-${ARCH}.dmg"

    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  Building ${ARCH} (${LABEL})"
    echo "════════════════════════════════════════════════════════════"

    # ── Build Release configuration (single arch) ────────────────────
    echo "Building Release (${ARCH})…"
    xcodebuild -project "${APP_NAME}.xcodeproj" \
        -scheme "${APP_NAME}" \
        -configuration Release \
        -destination "platform=macOS" \
        -derivedDataPath "${DD}" \
        ARCHS="${ARCH}" \
        ONLY_ACTIVE_ARCH=NO \
        CODE_SIGN_IDENTITY="-" \
        CODE_SIGNING_ALLOWED=NO \
        clean build 2>&1 | tail -5

    local BUILD_APP="${DD}/Build/Products/Release/${APP}"
    if [ ! -d "${BUILD_APP}" ]; then
        echo "Error: Build failed — ${APP} not found for ${ARCH}"
        exit 1
    fi
    echo "✓ Build succeeded (${ARCH})"

    # ── Copy to dist/<arch>/ ─────────────────────────────────────────
    mkdir -p "${OUT_DIR}"
    rm -rf "${OUT_APP}"
    cp -R "${BUILD_APP}" "${OUT_APP}"
    echo "✓ Copied to dist/${ARCH}/${APP}"

    # ── Copy Assets.car for macOS 26+ icon support ───────────────────
    if [ -f "${REPO_ROOT}/Assets.car" ]; then
        cp "${REPO_ROOT}/Assets.car" "${OUT_APP}/Contents/Resources/Assets.car"
        echo "✓ Assets.car copied"
    fi

    # ── Confirm the binary is truly single-slice ─────────────────────
    echo "  Architectures: $(lipo -archs "${OUT_APP}/Contents/MacOS/${APP_NAME}")"

    # ── Strip symbols (shrinks __LINKEDIT; must run before signing) ───
    echo "Stripping symbols…"
    strip -rSTx "${OUT_APP}/Contents/MacOS/${APP_NAME}"
    echo "✓ Stripped"

    # ── Code signing ─────────────────────────────────────────────────
    echo "Signing (${ARCH})…"
    local SIGN_OPTS=(--force --sign "${CODESIGN_ID}" --options runtime --timestamp)

    echo "  Signing main executable…"
    codesign "${SIGN_OPTS[@]}" --entitlements "${ENTITLEMENTS}" "${OUT_APP}/Contents/MacOS/${APP_NAME}"

    echo "  Signing app bundle…"
    codesign "${SIGN_OPTS[@]}" --entitlements "${ENTITLEMENTS}" "${OUT_APP}"

    echo "✓ Signing complete"

    # ── Verify ───────────────────────────────────────────────────────
    echo "Verifying…"
    codesign --verify --deep --strict "${OUT_APP}" 2>&1 || {
        echo "Warning: Signature verification issues (expected with ad-hoc)"
    }

    # ── Create DMG ───────────────────────────────────────────────────
    echo "Creating DMG…"
    rm -f "${DMG_PATH}"
    hdiutil create -volname "Type Proofing (${LABEL})" \
        -srcfolder "${OUT_APP}" \
        -ov -format UDZO \
        "${DMG_PATH}" 2>/dev/null

    if [ "${CODESIGN_ID}" != "-" ]; then
        codesign --force --sign "${CODESIGN_ID}" --options runtime --timestamp "${DMG_PATH}"
    fi

    echo "✓ DMG created: ${DMG_PATH}"

    # ── Notarize (optional) ──────────────────────────────────────────
    if [ "${NOTARIZE:-0}" = "1" ] && [ "${CODESIGN_ID}" != "-" ]; then
        echo "Submitting for notarization (${ARCH})…"

        local NOTARY_RC=0
        local NOTARY_AUTH=""
        local NOTARY_OUTPUT
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

        local SUBMISSION_ID NOTARY_STATUS
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

    # ── Report ───────────────────────────────────────────────────────
    local APP_SIZE DMG_SIZE
    APP_SIZE=$(du -sh "${OUT_APP}" | cut -f1)
    echo "  ${ARCH} app: ${OUT_APP} (${APP_SIZE})"
    if [ -f "${DMG_PATH}" ]; then
        DMG_SIZE=$(du -sh "${DMG_PATH}" | cut -f1)
        echo "  ${ARCH} DMG: ${DMG_PATH} (${DMG_SIZE})"
    fi
}

# ── Run builds ───────────────────────────────────────────────────────
mkdir -p "${DIST_DIR}"

# Optional first arg selects a single architecture; default builds both.
case "${1:-all}" in
    arm64)  build_and_package arm64  "Apple Silicon" ;;
    x86_64) build_and_package x86_64 "Intel" ;;
    all)
        build_and_package arm64  "Apple Silicon"
        build_and_package x86_64 "Intel"
        ;;
    *)
        echo "Error: unknown architecture '${1}'. Use arm64, x86_64, or omit for both."
        exit 1
        ;;
esac

echo ""
echo "=== Build complete ==="
