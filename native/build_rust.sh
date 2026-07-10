#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

# wordsiv's own suite is excluded for now: its default `python` feature pulls
# in pyo3, which the app build never uses. tp-bridge's tests exercise wordsiv
# through the FFI with the shipping feature set.
echo "==> Running tests..."
cargo test -p tp-bridge -p tp-fonts

echo "==> Building aarch64-apple-darwin (release)..."
cargo build --release --target aarch64-apple-darwin -p tp-bridge

echo "==> Building x86_64-apple-darwin (release)..."
cargo build --release --target x86_64-apple-darwin -p tp-bridge

echo "==> Creating universal2 binary..."
mkdir -p lib
lipo -create \
    target/aarch64-apple-darwin/release/libtpbridge.a \
    target/x86_64-apple-darwin/release/libtpbridge.a \
    -output lib/libtpnative.a

echo "==> Generating C header..."
mkdir -p include
cbindgen -c tp-bridge/cbindgen.toml tp-bridge/ -o include/tpnative.h

echo "==> Done."
lipo -info lib/libtpnative.a
echo "Header: include/tpnative.h"
