# Release checklist

## Repository launch

- Create a public repository named `radial-bridges` under your chosen account. Nothing has been published automatically.
- Upload/commit the contents of this directory, including `.github`, not its parent wrapper folder.
- Set About to: **Local radial-bridge G-code preview and post-processing for Bambu Studio.**
- Topics: `3d-printing`, `bambu-studio`, `gcode`, `bridging`, `pyside6`, `windows`, `calibration`.
- Enable Issues and private vulnerability reporting. Protect the default branch and require tests for merges.
- Upload `docs/assets/social-preview.png` in repository Settings → Social preview.
- Do not upload signing keys, user slices, runtime binaries, or scratch/build folders to the source repository.

## Release candidate validation

- [ ] Unit tests and offscreen GUI test pass.
- [ ] All prior features are present; preview memory works at two heights with different settings.
- [ ] Install/upgrade/uninstall tested on clean Windows 10/11 x64.
- [ ] Launch via shortcut and hook; confirm native icon, no console, exit codes.
- [ ] Re-slice in your current Bambu Studio, inspect final export and backup.
- [ ] Test actual material/nozzle/layer combinations; document print settings and results without claiming general safety.
- [ ] Review licenses, dependency notices, and source availability for LGPL components.
- [ ] Sign launcher before packing; sign installer afterward; verify signatures and timestamp.
- [ ] Compute SHA-256 after signing and final asset naming.
- [ ] Publish a Git tag only when its source matches the built payload.

## Release text

Title: **Radial Bridges 1.7.1 — Fine tuning & multi-height previews**

Body: use `docs/RELEASE-NOTES.md`. Attach the final setup EXE, source ZIP, and final `SHA256SUMS.txt`. Mark the first public build as a pre-release until Windows/Studio/print gates are complete. The supplied candidate is unsigned; do not replace that statement with “signed” until verification succeeds.

GitHub provenance and hashes supplement Authenticode; they do not provide a Windows trusted-publisher signature. Do not promise warning-free installation.
