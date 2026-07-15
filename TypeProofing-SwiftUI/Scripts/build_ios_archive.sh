#!/bin/bash
#
# Archives the iPad app for distribution or device installs.
#
# Usage:
#   bash Scripts/build_ios_archive.sh                # sign with the default team
#   DEVELOPMENT_TEAM=XXXXXXXXXX bash Scripts/build_ios_archive.sh
#
# Output: dist/TypeProofing-iOS.xcarchive
# Export an .ipa afterwards via Xcode Organizer, or:
#   xcodebuild -exportArchive -archivePath dist/TypeProofing-iOS.xcarchive \
#     -exportOptionsPlist <options.plist> -exportPath dist/
#
# Prerequisites:
#   1. ProofCore/Binaries/TPNative.xcframework built (native/build_rust.sh)
#   2. xcodegen installed (brew install xcodegen)
#   3. An Apple Developer team with an Apple Development certificate

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$PROJECT_DIR")"
DIST_DIR="${REPO_ROOT}/dist"

TEAM="${DEVELOPMENT_TEAM:-8YVTA46P66}"
ARCHIVE_PATH="${DIST_DIR}/TypeProofing-iOS.xcarchive"

echo "=== Type Proofing — iOS Archive ==="
echo "  Team:    ${TEAM}"
echo "  Archive: ${ARCHIVE_PATH}"
echo ""

# ── 0. Build TPNative.xcframework if missing ─────────────────────────
if [ ! -d "${REPO_ROOT}/ProofCore/Binaries/TPNative.xcframework" ]; then
    echo "TPNative.xcframework not found — building from Rust sources…"
    bash "${REPO_ROOT}/native/build_rust.sh"
fi

# ── 1. Regenerate Xcode project ──────────────────────────────────────
cd "${PROJECT_DIR}"
xcodegen generate --spec project.yml 2>/dev/null || {
    echo "Error: xcodegen failed. Install with: brew install xcodegen"
    exit 1
}

# ── 2. Archive ───────────────────────────────────────────────────────
mkdir -p "${DIST_DIR}"
rm -rf "${ARCHIVE_PATH}"
xcodebuild archive \
    -project TypeProofing.xcodeproj \
    -scheme TypeProofing \
    -destination "generic/platform=iOS" \
    -archivePath "${ARCHIVE_PATH}" \
    DEVELOPMENT_TEAM="${TEAM}" \
    -allowProvisioningUpdates \
    2>&1 | tail -5

echo ""
echo "✓ Archive written to ${ARCHIVE_PATH}"
