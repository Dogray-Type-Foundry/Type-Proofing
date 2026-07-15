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

echo "==> Building aarch64-apple-ios (release)..."
IPHONEOS_DEPLOYMENT_TARGET=17.0 cargo build --release --target aarch64-apple-ios -p tp-bridge

echo "==> Building aarch64-apple-ios-sim (release)..."
IPHONEOS_DEPLOYMENT_TARGET=17.0 cargo build --release --target aarch64-apple-ios-sim -p tp-bridge

echo "==> Building x86_64-apple-ios (simulator, release)..."
IPHONEOS_DEPLOYMENT_TARGET=17.0 cargo build --release --target x86_64-apple-ios -p tp-bridge

echo "==> Creating universal2 binary (macOS)..."
mkdir -p lib
lipo -create \
    target/aarch64-apple-darwin/release/libtpbridge.a \
    target/x86_64-apple-darwin/release/libtpbridge.a \
    -output lib/libtpnative.a

echo "==> Generating C header..."
mkdir -p include
cbindgen -c tp-bridge/cbindgen.toml tp-bridge/ -o include/tpnative.h

# Never lipo device + simulator slices — same arch, different platform.
# -create-xcframework keeps them as separate slices. Same-platform archs
# (the two simulator archs) do get lipo'd together.
# Stage iOS libs under the libtpnative.a name so every slice matches the
# modulemap's `link "tpnative"` directive.
echo "==> Creating TPNative.xcframework..."
mkdir -p lib/ios lib/ios-sim
cp target/aarch64-apple-ios/release/libtpbridge.a lib/ios/libtpnative.a
lipo -create \
    target/aarch64-apple-ios-sim/release/libtpbridge.a \
    target/x86_64-apple-ios/release/libtpbridge.a \
    -output lib/ios-sim/libtpnative.a
rm -rf lib/TPNative.xcframework
xcodebuild -create-xcframework \
    -library lib/libtpnative.a -headers include \
    -library lib/ios/libtpnative.a -headers include \
    -library lib/ios-sim/libtpnative.a -headers include \
    -output lib/TPNative.xcframework

echo "==> Copying XCFramework into ProofCore..."
rm -rf ../ProofCore/Binaries/TPNative.xcframework
cp -R lib/TPNative.xcframework ../ProofCore/Binaries/TPNative.xcframework

echo "==> Done."
lipo -info lib/libtpnative.a
echo "Header: include/tpnative.h"
echo "XCFramework: ProofCore/Binaries/TPNative.xcframework"
