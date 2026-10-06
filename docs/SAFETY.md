# Scope, assumptions, and limitations

- Input must be plain text G-code or sliced 3MF containing plate G-code, up to 150 MiB.
- Complete narrow rings are required. Cutouts, partial rings, unrelated objects, and inconsistent flow can be refused.
- XYZ must be known, in millimeters, and absolute. M82/M83 extrusion and G92 E resets are parsed.
- XY arcs require incremental I/J centers. R arcs and other planes are not supported.
- Balanced, tested source wipe/Z-hop patterns are handled; printer-specific unknown state commands are refused inside rewritten spans.
- Supporting layers are not inspected. Endpoint support, adhesion, cooling, material, nozzle, collision clearance, and mechanical strength remain the user's responsibility.
- Monotonic patterns contain travel. Preview drawings show extrusion only, not a full printer simulation.
- Increasing width, extra flow, or density increases material and can exceed the hotend's capacity. There is no automatic volumetric-flow limiter.
- Spoke density changes generated line count; line spacing still participates in source geometry validation. It is not an arbitrary override of a missing sector.
- Source firmware motion/pressure behavior is not fully modeled. The converter validates its own supported subset, not every printer dialect.
- Multi-height conversions must not select overlapping or interleaved source ranges. Separate tools at the same height require separate processing outside the combined-height workflow.
- Manual mode creates a new G-code file. Studio hook mode rewrites its supplied working file after making a backup.
- Session previews are not saved when the app closes. Profiles are geometry-specific and retain settings for hook use.
- No physical print has been validated by the build environment. Tests are regression evidence, not certification.

Do not bypass a refusal without understanding the machine-state effects. Inspect the final exported file, not only the original slicer preview.
