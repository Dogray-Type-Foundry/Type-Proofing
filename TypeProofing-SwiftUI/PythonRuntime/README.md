# PythonRuntime

This directory holds the repo-built CPython framework used by the macOS app.

The generated framework is intentionally not committed:

```text
TypeProofing-SwiftUI/PythonRuntime/Python.framework
```

Build it with:

```bash
bash TypeProofing-SwiftUI/Scripts/build_python_framework.sh
```

Runtime target:

- CPython: 3.14.5
- Build: standard GIL framework build
- Architectures: universal2 (`x86_64 arm64`)
- macOS deployment target: 13.0
- Source: `https://www.python.org/ftp/python/3.14.5/Python-3.14.5.tar.xz`
- SHA-256: `7e32597b99e5d9a39abed35de4693fa169df3e5850d4c334337ffd6a19a36db6`

The build script downloads and verifies the source tarball, builds into ignored
repo-local directories, copies the staged framework to `Python.framework`, then
prunes non-runtime stdlib content before Xcode embeds it.

Intentionally omitted from the final framework:

- `tkinter`
- `idlelib`
- `test`
- `ensurepip`
- `sqlite3`
- `ssl`
- `_hashlib` OpenSSL extension
- framework site-packages
- CPython build headers and config files

If future proof generation needs Python HTTPS/networking or SQLite access,
revisit the `ssl` and `sqlite3` pruning rules before shipping that feature.

For future Python patch updates, change `PYTHON_VERSION` and
`SOURCE_SHA256` in `Scripts/build_python_framework.sh`, rebuild the framework,
rebuild `python-packages`, run the import and test checks from
`PYTHON_3_14_FRAMEWORK_PLAN.md`, and verify the packaged app still signs.
