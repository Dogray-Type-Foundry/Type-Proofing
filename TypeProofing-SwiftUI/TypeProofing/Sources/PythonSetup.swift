import Foundation
import PythonKit

/// One-time Python runtime initialization.
///
/// Must be called **before** any `Python.import()` call. Sets up:
/// - `PYTHON_LIBRARY`  — points PythonKit at the bundled `libpython3.14.dylib`
/// - `PYTHONHOME`      — tells Python where its standard library lives
/// - `sys.path`        — adds the `python-lib` resource folder so our
///                        `.py` modules and vendored packages are importable
enum PythonSetup {

    /// Whether `initialize()` has already run.
    private static var isInitialized = false

    static func initialize() {
        guard !isInitialized else { return }
        isInitialized = true

        // ── 1. Locate paths inside the app bundle ──────────────────────
        guard let frameworksPath = Bundle.main.privateFrameworksPath,
              let resourcePath   = Bundle.main.resourcePath else {
            fatalError("Cannot resolve app bundle paths")
        }

        let pythonDylib  = frameworksPath + "/Python.framework/Versions/3.14/lib/libpython3.14.dylib"
        let pythonHome   = frameworksPath + "/Python.framework/Versions/3.14"
        let pythonLibDir = resourcePath   + "/python-lib"

        // ── 2. Environment variables (must be set before first Python use) ─
        setenv("PYTHON_LIBRARY", pythonDylib, 1)
        setenv("PYTHONHOME",     pythonHome,  1)

        // Prevent Python from looking for a user site-packages dir
        setenv("PYTHONNOUSERSITE", "1", 1)

        // ── 3. Extend sys.path ──────────────────────────────────────────
        let sys = Python.import("sys")
        sys.path.insert(0, pythonLibDir)
    }
}
