#!/bin/bash
# copy_python_sources.sh
#
# Xcode "Run Script" build phase — copies the Python engine sources and
# vendored packages into Resources/python-lib inside the app bundle.

set -euo pipefail

PYTHON_LIB_DIR="${BUILT_PRODUCTS_DIR}/${CONTENTS_FOLDER_PATH}/Resources/python-lib"
mkdir -p "${PYTHON_LIB_DIR}"

# ── 1. Python engine sources (from the repo root) ──────────────────────
# SRCROOT for the xcode project is TypeProofing-SwiftUI/; the Python
# sources live in the python/ directory one level up.
PYTHON_SRC="${SRCROOT}/../python"

PYTHON_FILES=(
    engine.py
    generation_config.py
    diagnostics.py
    worker.py
    proof.py
    fonts.py
    config.py
    settings.py
    pdf_manager.py
    markup_parser.py
    opentype_substitutions.py
    sample_texts.py
    script_texts.py
    accented_dictionary.py
    text_generators.py
)

for f in "${PYTHON_FILES[@]}"; do
    cp "${PYTHON_SRC}/${f}" "${PYTHON_LIB_DIR}/"
done

# Data files
cp "${PYTHON_SRC}/AdobeBlank.otf"  "${PYTHON_LIB_DIR}/" 2>/dev/null || true
cp "${PYTHON_SRC}/eng_wiki.tsv"    "${PYTHON_LIB_DIR}/" 2>/dev/null || true

# ── 2. Vendored Python packages ────────────────────────────────────────
PACKAGES_DIR="${SRCROOT}/python-packages"

if [ -d "${PACKAGES_DIR}" ]; then
    # Core packages needed by engine.py / proof.py / fonts.py
    PACKAGE_DIRS=(
        drawBot
        drawBotGrid
        wordsiv
        fontTools
        PIL
        pyclipper
        booleanOperations
        jaraco
        more_itertools
        packaging
        platformdirs
        backports

        # PyObjC core + framework bridges required by DrawBot at runtime
        objc
        PyObjCTools
        AppKit
        ApplicationServices
        Carbon
        CoreFoundation
        CoreText
        ExceptionHandling
        Foundation
        Quartz
        LaunchServices
    )

    for pkg in "${PACKAGE_DIRS[@]}"; do
        if [ -d "${PACKAGES_DIR}/${pkg}" ]; then
            cp -R "${PACKAGES_DIR}/${pkg}" "${PYTHON_LIB_DIR}/"
        fi
    done

    # Copy PyObjC native extensions (.so files) at the top level
    find "${PACKAGES_DIR}" -maxdepth 1 -name '*.so' -exec cp {} "${PYTHON_LIB_DIR}/" \;
    find "${PACKAGES_DIR}" -maxdepth 1 -name '*.dylib' -exec cp {} "${PYTHON_LIB_DIR}/" \;
else
    echo "warning: python-packages/ not found at ${PACKAGES_DIR} — run Scripts/bundle_python_packages.sh first"
fi

echo "✓ Python sources copied to ${PYTHON_LIB_DIR}"
