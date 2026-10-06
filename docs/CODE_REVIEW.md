# Release review — 1.7.1 candidate

This is a focused source review and regression-test pass, not an independent security audit or print certification.

Validation result: 27 unit tests and the offscreen Qt GUI smoke test passed.
The installer payload was byte-compared against the reviewed Python source.
Windows-native execution, trusted signing and physical-print verification remain pending.

## Fixed

| Finding | Change | Regression coverage |
| --- | --- | --- |
| A selected subset retained all members for its selection dialog, and the hook profile used every member | Filter profile signatures to selected region IDs | Selected-subset profile test |
| Clockwise order reversed the first spoke too | Keep the first spoke, then traverse remaining angles in reverse | First-spoke/direction comparison |
| Unknown M-codes were assumed safe because they did not affect the local parser | Explicit allowlist; tested M991 preserved, unknown commands refused | Unknown state commands and firmware retract rejection |
| Interleaved multi-height replacements could invalidate source block numbering | Reject interleaved ranges and duplicate-height configs | Conflicting-target tests |

## Preserved

The recovered 1.5.1 pattern, bridge-width, calibration, continuous-ring, Zoom/Fit, hover help, error handling and Windows identity implementation remains the baseline. The 1.6.1 multi-height memory/export and 1.7.0 Fine tuning controls remain included.

## Remaining limitations / useful next improvements

1. Validate native Windows install, Studio version behavior, and real printer output before public stable release.
2. Add an optional supporting-layer check and volumetric-flow warning; neither exists today.
3. Improve parsing coverage with captured, permission-cleared printer-specific fixtures. The user slice is not included in this repository.
4. Add resumable project/session files; current preview memory lasts only until close/load/clear.
5. Replace repeated full-file parsing for very large multi-height jobs with a single validated edit plan.
6. Add tests for firmware state changes outside selected spans. The app is not a complete G-code interpreter.
7. Review dependency updates independently; pinned older dependencies are reproducible, not a claim of current vulnerability-free status.
8. Obtain a trusted signing identity, run signing on Windows, verify both signatures, and regenerate checksums.

Release gate: public stable distribution should wait for native Windows testing and a documented maintainer decision on unsigned versus signed publication.
