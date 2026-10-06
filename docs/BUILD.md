# Build and test

Python 3.10+ is required for development. The installer bundles Python 3.12.10 and PySide6 Essentials 6.8.3 for Windows x64. Runtime archives have pinned SHA-256 values in `dependencies.json`.

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s payload -v
python gui_smoke.py
```

The GUI smoke test uses offscreen Qt and mocked Bambu launch. Run the real app with `python payload/app.py` to inspect it. Core hook mode does not import Qt.

## Windows installer

Install NSIS 3.x separately. From the repository root:

```sh
python build_windows.py --makensis "C:/Program Files (x86)/NSIS/makensis.exe"
```

The script downloads pinned Windows dependencies, verifies checksums, compiles the icon-bearing native launcher using Zig, and builds a per-user NSIS installer. Linux cross-builds require NSIS and `--makensis /path/to/makensis`; some unpacked NSIS distributions also require `NSISDIR`.

Building is not signing. Use `--skip-installer` to build the launcher/runtime before signing and packing. See [SIGNING.md](SIGNING.md) before public distribution. Do not commit the bundled runtime or installers into source control. Attach release assets through GitHub Releases.

Native Windows installation, real Bambu integration, and physical prints must be checked separately. Linux GUI tests cannot establish those outcomes.
