#!/bin/bash
#
# Builds the iPad app (Release, signed) and installs it on a connected iPad.
#
# Usage:
#   bash Scripts/deploy_ipad.sh                 # first paired iPad found
#   bash Scripts/deploy_ipad.sh <device-id>     # a specific device
#
# Prerequisites:
#   - iPad paired with this Mac (cable or Wi-Fi) and Developer Mode enabled
#     (Settings > Privacy & Security > Developer Mode)
#   - ProofCore/Binaries/TPNative.xcframework built (native/build_rust.sh)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$PROJECT_DIR")"

DEVICE="${1:-}"
if [ -z "${DEVICE}" ]; then
    DEVICES_JSON=$(mktemp)
    xcrun devicectl list devices --json-output "${DEVICES_JSON}" >/dev/null 2>&1
    DEVICE=$(python3 -c "
import json, sys
data = json.load(open('${DEVICES_JSON}'))
for d in data['result']['devices']:
    props = d.get('hardwareProperties', {})
    if props.get('deviceType') == 'iPad':
        print(d['identifier']); break
" || true)
    rm -f "${DEVICES_JSON}"
    if [ -z "${DEVICE}" ]; then
        echo "Error: no paired iPad found. Pass a device identifier explicitly:"
        xcrun devicectl list devices
        exit 1
    fi
fi

echo "=== Type Proofing — Deploy to iPad ==="
echo "  Device: ${DEVICE}"
echo ""

# ── 0. Build TPNative.xcframework if missing ─────────────────────────
if [ ! -d "${REPO_ROOT}/ProofCore/Binaries/TPNative.xcframework" ]; then
    echo "TPNative.xcframework not found — building from Rust sources…"
    bash "${REPO_ROOT}/native/build_rust.sh"
fi

# ── 1. Regenerate project and build (Release, signed) ────────────────
cd "${PROJECT_DIR}"
xcodegen generate --spec project.yml 2>/dev/null || {
    echo "Error: xcodegen failed. Install with: brew install xcodegen"
    exit 1
}

DD="${PROJECT_DIR}/build-ios-deploy"
echo "Building Release for device…"
xcodebuild \
    -project TypeProofing.xcodeproj \
    -scheme TypeProofing \
    -configuration Release \
    -destination "generic/platform=iOS" \
    -derivedDataPath "${DD}" \
    -allowProvisioningUpdates \
    build 2>&1 | tail -3

APP="${DD}/Build/Products/Release-iphoneos/TypeProofing.app"
if [ ! -d "${APP}" ]; then
    echo "Error: built app not found at ${APP}"
    exit 1
fi

# ── 2. Install ───────────────────────────────────────────────────────
echo "Installing on device…"
xcrun devicectl device install app --device "${DEVICE}" "${APP}"

echo ""
echo "✓ Installed. Launch Type Proofing from the iPad home screen."
