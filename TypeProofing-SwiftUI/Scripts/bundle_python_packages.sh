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
REQUIREMENTS_FILE="${REPO_ROOT}/requirements.txt"
PYTHON_VERSION="3.14"
STAGE_PYTHON="${PROJECT_DIR}/PythonRuntime/stage/Library/Frameworks/Python.framework/Versions/${PYTHON_VERSION}/bin/python${PYTHON_VERSION}"
RUNTIME_PYTHON="${PROJECT_DIR}/PythonRuntime/Python.framework/Versions/${PYTHON_VERSION}/bin/python${PYTHON_VERSION}"

if [ -x "${STAGE_PYTHON}" ]; then
    PYTHON_BIN="${STAGE_PYTHON}"
elif [ -x "${RUNTIME_PYTHON}" ]; then
    PYTHON_BIN="${RUNTIME_PYTHON}"
else
    echo "Error: Python ${PYTHON_VERSION} framework interpreter not found."
    echo "Run: bash TypeProofing-SwiftUI/Scripts/build_python_framework.sh"
    exit 1
fi

if [ ! -f "${REQUIREMENTS_FILE}" ]; then
    echo "Error: requirements.txt not found at ${REQUIREMENTS_FILE}"
    exit 1
fi

USE_UV=0
if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import ssl
PY
then
    if command -v uv >/dev/null 2>&1; then
        USE_UV=1
    else
        echo "Error: ${PYTHON_BIN} does not provide ssl, and uv is not available."
        echo "Package downloads require a downloader with HTTPS support."
        exit 1
    fi
elif ! "${PYTHON_BIN}" -m pip --version >/dev/null 2>&1; then
    if ! "${PYTHON_BIN}" -m ensurepip --upgrade >/dev/null 2>&1; then
        echo "Error: pip is unavailable for ${PYTHON_BIN}."
        echo "Use the build-stage interpreter produced by build_python_framework.sh; the final runtime is pruned."
        exit 1
    fi
fi

echo "Installing Python packages into ${TARGET_DIR} ..."
echo "  Python: ${PYTHON_BIN}"
echo "  Requirements: ${REQUIREMENTS_FILE}"
rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"

# requirements.txt is the source of truth. It intentionally lists the specific
# PyObjC framework bridges DrawBot uses instead of the broad pyobjc meta-package.
# --no-deps keeps pip from expanding that bridge list behind our backs.
if [ "${USE_UV}" -eq 1 ]; then
    echo "  Installer: uv (Python ssl is unavailable)"
    UV_PYTHON_DOWNLOADS=never \
    MACOSX_DEPLOYMENT_TARGET="13.0" \
    ARCHFLAGS="-arch x86_64 -arch arm64" \
    uv pip install \
        --python "${PYTHON_BIN}" \
        --target "${TARGET_DIR}" \
        --no-deps \
        --requirement "${REQUIREMENTS_FILE}"
else
    echo "  Installer: python -m pip"
    MACOSX_DEPLOYMENT_TARGET="13.0" \
    ARCHFLAGS="-arch x86_64 -arch arm64" \
    "${PYTHON_BIN}" -m pip install \
        --target="${TARGET_DIR}" \
        --no-deps \
        --requirement "${REQUIREMENTS_FILE}"
fi

if find "${TARGET_DIR}" -name '*cpython-313-darwin.so' -print -quit | grep -q .; then
    echo "Error: Python 3.13 native extension found in ${TARGET_DIR}"
    find "${TARGET_DIR}" -name '*cpython-313-darwin.so'
    exit 1
fi

echo ""
echo "✓ Packages installed to ${TARGET_DIR}"
echo "  Native extensions:"
find "${TARGET_DIR}" -maxdepth 6 -name "*.so" -print
echo "  You can now build the Xcode project."
