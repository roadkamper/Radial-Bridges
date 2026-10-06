# Radial Bridges 1.7.1 — Fine tuning & multi-height previews

An experimental Windows x64 tool for turning eligible circular-ring bridges into inspectable radial paths for Bambu Studio.

## Highlights

- Connected Zigzag and monotonic inward/outward patterns.
- Independent settings and remembered previews at multiple bridge heights.
- Combined export and geometry-matched Studio hook profiles.
- Adjustable bridge width, extra flow, density, turn flow/speed, travel/retract speed, layout direction and other advanced controls.
- Width-calibration sectors, pointer-anchored zoom, pan/Fit, hover help, Clear model, and copyable errors.

## Review fixes

Profiles now honor selected subsets. Clockwise printing retains the requested first spoke. Unknown firmware commands are no longer assumed safe. Conflicting multi-height selections are rejected before writing.

## Install

Download the setup EXE, verify its hash, close any old Radial Bridges window, and run setup. Python is bundled. Open an original sliced G-code or sliced G-code 3MF. Generate each desired height and inspect the saved result in Studio before printing.

**Signing status: this prepared candidate is unsigned.** The maintainer must update this statement only after trusted Authenticode signing and verification. SHA-256 files establish integrity against a trusted published hash, not publisher identity.

## Important limits

Complete narrow annular bridges only. Support under bridge endpoints is not verified. Preview omits travel. Fan, temperature, acceleration, pressure advance and layer height remain in Studio. No universal print-quality claim, native Windows certification, or comprehensive security audit is made.

Please report bugs with app version, Studio version, printer/nozzle/material, exact error text, and a minimal synthetic slice if possible. Do not post private or proprietary G-code publicly.
