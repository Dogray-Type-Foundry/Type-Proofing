#!/bin/bash
# Build and prune the embedded CPython framework used by Type Proofing.
#
# Run from the repo root:
#   bash TypeProofing-SwiftUI/Scripts/build_python_framework.sh

set -euo pipefail

PYTHON_VERSION="3.14.5"
PYTHON_SHORT_VERSION="3.14"
DEPLOYMENT_TARGET="13.0"
SOURCE_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz"
SOURCE_SHA256="7e32597b99e5d9a39abed35de4693fa169df3e5850d4c334337ffd6a19a36db6"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RUNTIME_DIR="${PROJECT_DIR}/PythonRuntime"
SRC_DIR="${RUNTIME_DIR}/src"
BUILD_DIR="${RUNTIME_DIR}/build"
STAGE_DIR="${RUNTIME_DIR}/stage"
OUTPUT_FW="${RUNTIME_DIR}/Python.framework"
TARBALL="${SRC_DIR}/Python-${PYTHON_VERSION}.tar.xz"
SOURCE_DIR="${SRC_DIR}/Python-${PYTHON_VERSION}"
STAGED_FW="${STAGE_DIR}/Library/Frameworks/Python.framework"
STAGED_PYTHON="${STAGED_FW}/Versions/${PYTHON_SHORT_VERSION}/Python"
OUTPUT_PYTHON="${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/Python"
OUTPUT_PYTHON_EXE="${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/bin/python${PYTHON_SHORT_VERSION}"
OUTPUT_PYTHON_APP_EXE="${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/Resources/Python.app/Contents/MacOS/Python"
OUTPUT_LIBPYTHON="${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/lib/libpython${PYTHON_SHORT_VERSION}.dylib"
OUTPUT_STDLIB="${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/lib/python${PYTHON_SHORT_VERSION}"
OPENSSL_DIR=""

require_tool() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Error: required tool not found: $1" >&2
        exit 1
    fi
}

remove_path() {
    rm -rf "$1" 2>/dev/null || true
}

echo "=== Build CPython ${PYTHON_VERSION} framework ==="
echo "  Runtime dir: ${RUNTIME_DIR}"
echo "  Output:      ${OUTPUT_FW}"
echo ""

for tool in curl shasum tar xcrun make sysctl lipo install_name_tool otool ditto; do
    require_tool "${tool}"
done

for candidate in /opt/homebrew/opt/openssl@3 /opt/homebrew/opt/openssl /usr/local/opt/openssl@3 /usr/local/opt/openssl; do
    if [ -d "${candidate}/include/openssl" ]; then
        OPENSSL_DIR="${candidate}"
        break
    fi
done

if [ -n "${OPENSSL_DIR}" ]; then
    echo "  Build-stage OpenSSL: ${OPENSSL_DIR}"
else
    echo "  Build-stage OpenSSL: not found; pip downloads may be unavailable"
fi

mkdir -p "${SRC_DIR}"

if [ ! -f "${TARBALL}" ]; then
    echo "Downloading ${SOURCE_URL} ..."
    curl --fail --location --remote-time --output "${TARBALL}" "${SOURCE_URL}"
fi

ACTUAL_SHA256="$(shasum -a 256 "${TARBALL}" | awk '{print $1}')"
if [ "${ACTUAL_SHA256}" != "${SOURCE_SHA256}" ]; then
    echo "Error: checksum mismatch for ${TARBALL}" >&2
    echo "  expected: ${SOURCE_SHA256}" >&2
    echo "  actual:   ${ACTUAL_SHA256}" >&2
    exit 1
fi
echo "✓ Source checksum verified"

rm -rf "${SOURCE_DIR}" "${BUILD_DIR}" "${STAGE_DIR}" "${OUTPUT_FW}"
mkdir -p "${BUILD_DIR}" "${STAGE_DIR}"

echo "Extracting source ..."
tar -xJf "${TARBALL}" -C "${SRC_DIR}"

SDK_PATH="$(xcrun --sdk macosx --show-sdk-path)"
JOBS="$(sysctl -n hw.ncpu)"

echo "Configuring universal2 framework ..."
(
    cd "${BUILD_DIR}"
    CONFIGURE_ARGS=(
        --enable-framework="${STAGE_DIR}/Library/Frameworks"
        --enable-universalsdk="${SDK_PATH}"
        --with-universal-archs=universal2
        --without-static-libpython
        --with-app-store-compliance
    )
    if [ -n "${OPENSSL_DIR}" ]; then
        CONFIGURE_ARGS+=(--with-openssl="${OPENSSL_DIR}" --with-openssl-rpath=no)
    fi
    MACOSX_DEPLOYMENT_TARGET="${DEPLOYMENT_TARGET}" \
    CPPFLAGS="${OPENSSL_DIR:+-I${OPENSSL_DIR}/include}" \
    LDFLAGS="${OPENSSL_DIR:+-L${OPENSSL_DIR}/lib}" \
    PKG_CONFIG_PATH="${OPENSSL_DIR:+${OPENSSL_DIR}/lib/pkgconfig:}${PKG_CONFIG_PATH:-}" \
    "${SOURCE_DIR}/configure" "${CONFIGURE_ARGS[@]}"
)

echo "Building ..."
make -C "${BUILD_DIR}" -j"${JOBS}"

echo "Installing into stage ..."
make -C "${BUILD_DIR}" install

if [ ! -f "${STAGED_PYTHON}" ]; then
    echo "Error: expected staged framework binary not found: ${STAGED_PYTHON}" >&2
    exit 1
fi

echo "Verifying staged architectures ..."
lipo -archs "${STAGED_PYTHON}"
lipo -archs "${STAGED_FW}/Versions/${PYTHON_SHORT_VERSION}/lib/libpython${PYTHON_SHORT_VERSION}.dylib"

echo "Copying framework to runtime output ..."
ditto "${STAGED_FW}" "${OUTPUT_FW}"

echo "Pruning runtime framework ..."
remove_path "${OUTPUT_STDLIB}/test"
remove_path "${OUTPUT_STDLIB}/idlelib"
remove_path "${OUTPUT_STDLIB}/ensurepip"
remove_path "${OUTPUT_STDLIB}/tkinter"
remove_path "${OUTPUT_STDLIB}/turtledemo"
remove_path "${OUTPUT_STDLIB}/turtle.py"
remove_path "${OUTPUT_STDLIB}/sqlite3"
remove_path "${OUTPUT_STDLIB}/ssl.py"
remove_path "${OUTPUT_STDLIB}/site-packages"
remove_path "${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/include"
remove_path "${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/share"
remove_path "${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/Resources/English.lproj/Documentation"
remove_path "${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/Frameworks/Tcl.framework"
remove_path "${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/Frameworks/Tk.framework"
rmdir "${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/Frameworks" 2>/dev/null || true

find "${OUTPUT_FW}/Versions/${PYTHON_SHORT_VERSION}/bin" -mindepth 1 \
    ! -name "python${PYTHON_SHORT_VERSION}" \
    -exec rm -rf {} + 2>/dev/null || true
rm -rf "${OUTPUT_STDLIB}"/config-* 2>/dev/null || true
rm -f "${OUTPUT_STDLIB}"/lib-dynload/_sqlite3*.so 2>/dev/null || true
rm -f "${OUTPUT_STDLIB}"/lib-dynload/_ssl*.so 2>/dev/null || true
rm -f "${OUTPUT_STDLIB}"/lib-dynload/_hashlib*.so 2>/dev/null || true
rm -f "${OUTPUT_STDLIB}"/lib-dynload/_tkinter*.so 2>/dev/null || true
rm -f "${OUTPUT_STDLIB}"/lib-dynload/_test*.so 2>/dev/null || true
find "${OUTPUT_FW}" -name '*.a' -delete 2>/dev/null || true
find "${OUTPUT_FW}" -name '*.pyc' -delete 2>/dev/null || true
find "${OUTPUT_FW}" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT_FW}" -name 'pkgconfig' -type d -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT_FW}" -name '*Config.sh' -delete 2>/dev/null || true

echo "Fixing framework install names ..."
install_name_tool -id "@rpath/Python.framework/Versions/${PYTHON_SHORT_VERSION}/Python" "${OUTPUT_PYTHON}"
if [ -f "${OUTPUT_PYTHON_EXE}" ]; then
    install_name_tool -change "${STAGED_PYTHON}" "@executable_path/../Python" "${OUTPUT_PYTHON_EXE}"
fi
if [ -f "${OUTPUT_PYTHON_APP_EXE}" ]; then
    install_name_tool -change "${STAGED_PYTHON}" "@executable_path/../../../../Python" "${OUTPUT_PYTHON_APP_EXE}"
fi

echo "Verifying final framework ..."
lipo -archs "${OUTPUT_PYTHON}"
lipo -archs "${OUTPUT_LIBPYTHON}"
otool -D "${OUTPUT_PYTHON}"
otool -L "${OUTPUT_PYTHON}"
if [ -f "${OUTPUT_PYTHON_EXE}" ]; then
    otool -L "${OUTPUT_PYTHON_EXE}"
fi
if [ -f "${OUTPUT_PYTHON_APP_EXE}" ]; then
    otool -L "${OUTPUT_PYTHON_APP_EXE}"
fi
otool -L "${OUTPUT_LIBPYTHON}"

echo ""
echo "✓ Python.framework ready at ${OUTPUT_FW}"
echo "  Build-stage interpreter for vendoring packages:"
echo "  ${STAGED_FW}/Versions/${PYTHON_SHORT_VERSION}/bin/python${PYTHON_SHORT_VERSION}"
