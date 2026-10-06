# Changelog

## 1.7.1 — release candidate

- Fix selected-region profile generation to exclude unchecked regions.
- Keep the requested first spoke when printing clockwise.
- Reject overlapping/interleaved multi-height source ranges and duplicate physical-height configurations.
- Use an explicit preserved-command allowlist; reject unknown M-codes and firmware retract G10/G11 inside replacements.
- Add GitHub documentation, release/signing instructions, CI, issue templates, and original project assets.

## 1.7.0

- Add Fine tuning controls for bridge/turn flow, density, turn speed, travel/retraction speeds, start offset, direction, connection threshold, travel resolution, tolerance, and source width.

## 1.6.1

- Restore the actual 1.5.1 source baseline after the defective 1.6.0 build.
- Add independent previews/settings at multiple bridge heights and combined export/Studio profiles.

## 1.5.1

- Connected Zigzag, monotonic patterns, width adjustment, calibration, safe continuous-ring conversion, zoom/pan, hover help, clear model, copied errors, and Windows application identity.

Do not use 1.6.0: it was built from an older source tree and omitted features.
# 1.8.0

- New radial logo embedded in Windows app and installer icons.
- Click detected bridge regions at one height to select or exclude them, with orange/blue feedback.
- Preserve zoom, pan, tuning, and previews at other heights when selection changes.
- Select all regions button; existing checkbox selection remains available.
