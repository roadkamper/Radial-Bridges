# Radial Bridges — source and build notes

The installable Windows application is `RadialBridges-Setup.exe`. Users do not
need this source package, Python, a compiler, or NSIS to install it.

`payload/README.txt` explains usage and current limitations. This version targets
one complete narrow ring per selected height, including split regions and multiple
independently previewed Z heights in one export. It is not a general-purpose slicer.

## Files

- `payload/app.py`: PySide6 desktop GUI and command-line hook entry point.
- `payload/backend.py`: sliced-3MF input, geometry estimates, profile matching,
  backups and Bambu Studio launch integration.
- `payload/radial_bridges.py`: conservative G-code converter.
- `payload/test_*.py`: geometry/state and backend tests.
- `gui_smoke.py`: offscreen UI smoke test, with Bambu launch mocked.
- `launcher.c`: small Windows x64 executable that hosts the bundled Python
  interpreter in-process, preserving the Radial Bridges taskbar identity.
- `launcher.rc`: embedded Windows icon and executable version metadata.
- `installer.nsi`: per-user installer, shortcuts and uninstaller.
- `build_windows.py`: downloads pinned runtime dependencies and builds the EXEs.
- `dependencies.json`: SHA-256 checksums of the exact dependency archives.

## Build

Requirements: Python 3.10+, `ziglang==0.13.0`, NSIS 3.x, and network access to
Python.org and PyPI. The build can run on Linux or Windows. No proprietary
Windows compiler is needed.

```text
python -m pip install ziglang==0.13.0
python build_windows.py --makensis /path/to/makensis
```

On Windows, point `--makensis` at `makensis.exe`. The script creates the runtime
folder from the official Python embeddable distribution and PySide6 Essentials
Windows wheels. It verifies archive hashes before extraction. App and library
source/license links are included. Downloading the library source archives is
not needed for an ordinary build, because the unchanged libraries are bundled
as shared binaries that may be replaced with compatible builds.

## Test

On the development machine:

```text
python -m pip install PySide6-Essentials==6.8.3
python -m unittest discover -s payload -v
python gui_smoke.py
```

On Windows, the bundled conversion/backend tests can also be run with:

```text
RadialBridges.exe --self-test
```

The app's executable is a GUI subsystem executable, so a console is not shown
for normal use. Its exit code still propagates to callers such as Studio.

## Validation performed

Automated regression tests passed for synthetic G-code, M82/M83, coordinate/feed
restoration, conservation of deposited filament, shortest radial spans,
geometry refusals, 3MF reading, immutable input, matching profiles and backups. Split regions, XY arcs,
command preservation, exact diagnostics and Clear model have additional tests.
The Qt GUI smoke test passed loading, estimates, preview, saving, opening
arguments, multi-height profile creation, clipboard, restoring previews after
switching heights, and disabling only the changed height's stale preview.
Same-height selection, Clear model, cursor-anchored wheel zoom, drag pan, zoom
buttons, Fit/double-click reset, revised action label and input hover help were
exercised in the UI test. The 1.5.1 feature tests verify connected extruding Zigzag turns
without repeated source wipe retractions, both monotonic patterns, proportional
width/flow adjustment, multi-sector calibration sweeps, safe unknown M-code
preservation for the tested M991 command, Bambu G2/G3 P1 spiral Z-hop recognition, and one-pass reordering.
They also verify that continuation cleanup is travel-only and emits no phantom
second radial marker. The launcher resource contains the application icon and
version metadata. Additional 1.7.0 tests verify two independently configured Z
heights, restored previews/settings, combined G-code output, and multi-target
Bambu Studio hook profiles.
Features touching the annulus, object boundaries and incompatible commands stay
separate. The uploaded Z 7.08 mm slice was validated as one 932-spoke pass for
all three patterns. The report exposes pass count, physical Z, width and flow.
Screenshots were rendered and visually inspected on Linux.

The native PE launcher and NSIS installer were cross-built. Core Qt/CPython DLL
imports were checked for bundled dependencies. The installer archive was checked
and extracted files compared with the build payload. Windows runtime execution
was attempted but the build environment blocks Wine's Unix socket startup.
A real Windows installation and actual Bambu Studio/physical printer behavior
remain untested. Executables are unsigned.

## Licenses

Application code: MIT (`payload/LICENSE.txt`). Bundled Python/Qt/PySide/Shiboken
retain their own licenses (`payload/THIRD-PARTY-NOTICES.txt` and `payload/LICENSES/`).
The application uses dynamically linked Qt libraries and contains no restriction
on replacing or debugging modified versions of those libraries.
