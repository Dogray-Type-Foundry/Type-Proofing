#!/bin/bash
# bundle_python_packages.sh
#
# One-time setup: install the vendored Python packages into
# TypeProofing-SwiftUI/python-packages/ so the Xcode build phase
# can copy them into the app bundle.
#
# Run from the repo root:
#   bash TypeProofing-SwiftUI/Scripts/bundle_python_packages.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$PROJECT_DIR")"
TARGET_DIR="${PROJECT_DIR}/python-packages"

echo "Installing Python packages into ${TARGET_DIR} …"
rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"

# Install non-PyObjC packages normally (they pull only what they need)
pip3 install --target="${TARGET_DIR}" \
    "git+https://github.com/typemytype/drawbot" \
    "git+https://github.com/jmsole/drawbotgrid" \
    "${REPO_ROOT}/wheels/wordsiv-0.3.1-cp39-abi3-macosx_10_12_x86_64.macosx_11_0_arm64.macosx_10_12_universal2.whl" \
    "fonttools>=4.58.5" \
    "Pillow" \
    "booleanOperations" \
    "jaraco.text" \
    "more-itertools" \
    "platformdirs" \
    --no-deps

# Install PyObjC core + only the framework bridges DrawBot actually uses.
# Using --no-deps avoids pulling the entire pyobjc meta-package (~80+ bridges).
pip3 install --target="${TARGET_DIR}" --no-deps \
    "pyobjc-core" \
    "pyobjc-framework-Cocoa" \
    "pyobjc-framework-Quartz" \
    "pyobjc-framework-CoreText" \
    "pyobjc-framework-ApplicationServices" \
    "pyobjc-framework-ExceptionHandling" \
    "pyobjc-framework-Carbon" \
    "pyobjc-framework-LaunchServices"

# Now install the actual dependencies of the non-PyObjC packages
# (fonttools, Pillow, booleanOperations, etc. need their own deps)
pip3 install --target="${TARGET_DIR}" \
    "fonttools>=4.58.5" \
    "Pillow" \
    "booleanOperations" \
    "jaraco.text" \
    "more-itertools" \
    "platformdirs" \
    "backports.tarfile" \
    "packaging"

echo ""
echo "✓ Packages installed to ${TARGET_DIR}"
echo "  You can now build the Xcode project."
