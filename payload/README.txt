RADIAL BRIDGES 1.8.0 — WINDOWS 10/11 x64

START HERE
1. Run RadialBridges-Setup.exe. It installs for your account and adds shortcuts.
2. Open Radial Bridges, then Open sliced file. Choose a plain .gcode or an
   exported sliced .gcode.3mf. If a 3MF has several plates, choose one.
3. Choose your ring's bridge height. Same-height regions are combined.
   Use Choose regions to include/exclude individual bridge sections.
   The app estimates center, radii, line spacing and original bridge width.
   These are extrusion-path dimensions, not the outside CAD dimensions.
   Choose Zigzag, Monotonic outward or Monotonic inward. Bridge width scales
   extrusion flow. For a thin 0.08 mm bridge, 0.42 -> 0.55 mm is a useful
   starting test (about 131% bridge flow); inspect and tune for your material.
   Calibration sweep divides one ring into 3–9 width sectors. Widths increase
   counterclockwise from the 3 o'clock/rightmost point. The preview lists them.
4. Click Generate Radial Bridge Preview. The side-by-side views show the old and new
   deposition paths. Scroll over either view to zoom at the pointer, drag to
   pan, and use + / - / Fit or double-click to reset. Each view is independent.
   The text shows old/new maximum spans, spoke spacing and output pass count.
   A checkmark appears beside each generated height. Switch to another bridge
   height and generate it independently; switching back restores that height's
   settings and preview. Save and the Studio hook include every checkmarked height.
5. Click Save radial G-code, then Open result in Bambu Studio. If Studio is not
   detected automatically, select its bambu-studio.exe once.

Clear model resets the loaded file, selections and both previews without
deleting any source, exported files, or saved profiles.

There is no separate Python installation and no hand-edited settings file.

FINE TUNING
Advanced settings are independent for each generated height and included in
Studio hook profiles. Hover each control for its explanation. Reset fine tuning
resets advanced values without resetting the main pattern or bridge dimensions.
- Extra bridge flow: multiplies width-based extrusion; 100% is unchanged.
- Spoke density: 50–200% of the normal count; increases material with line count.
- Zigzag turn flow and speed: adjust only connected turns, not radial spokes.
- Travel and retract speeds: affect generated non-printing moves only.
- Start offset and clockwise: rotate the layout or reverse printing order.
- Max connected gap: controls when Zigzag connects versus travels.
- Travel curve segment length: trade smooth travel for G-code size.
- Geometry tolerance and source-width override: expert validation/flow controls.
Fan, temperature, acceleration, pressure advance and layer height remain in your
Studio preset. No support is added or verified by changing these controls.

USE DIRECTLY INSIDE BAMBU STUDIO
After a successful preview, click Use inside Bambu Studio, then Copy command.
In Bambu Studio enable Advanced settings and paste the command into
Process > Others > Post-processing scripts. Re-slice and inspect the exported
result. Studio supplies its working G-code file to the app automatically.

The command refers to a saved profile specific to the selected bridge geometry.
The app finds that geometry again even if the bridge block numbering changes.
If the model is moved, resized or sliced differently, create a new profile from
that new slice. Remove the hook from Studio when you are done with the project.
This app does not modify your Studio presets or machine settings files.

Manual mode saves a new plain .gcode; it leaves input .3mf and .gcode unchanged.
It does not rebuild .3mf packages. Studio's hook route lets Studio perform its
own packaging. Existing Studio previews or time estimates may be stale after
post-processing: inspect the actual exported paths before printing.

SCOPE
This version handles complete narrow annular bridges at multiple Z heights,
including rings split across multiple feature sections. Each physical height
keeps independent settings and a restorable preview. Different tools stay
separate. Compatible sections separated only by travel
are joined into one circular pass. When enabled, the continuous-pass option can
also move all ring bridges ahead of intervening same-height infill/walls, but
only after verifying those paths do not touch the ring annulus. The intervening
feature remains in its original place. Removed continuation sections are labeled
as travel-only so Bambu Studio does not show a phantom second bridge feature.
Object boundaries, incompatible commands,
unbalanced extrusion, or features touching the annulus keep separate passes.
The preview explicitly reports pass count and exact Z height.
Each replaced section restores its own position, feedrate and extrusion state.
Common fan commands, acceleration commands, M400 waits, M73 progress, M900
pressure settings and G4 dwells are retained in order at equivalent progress.
In Zigzag mode, neighboring spokes are joined by short extruded turns. Obsolete
source wipe retractions and Z-hops are consumed instead of replayed inside that
continuous path. Monotonic modes retain compatible balanced source travel events.
Explicitly supported commands, including tested Bambu M991, are retained.
Unknown M-codes and firmware retract G10/G11 are refused. Tool/conditional
commands, volumetric E mode and unknown G-codes remain explicit refusals because
relocating them could produce unsafe G-code. Bambu G2/G3 P1 spiral Z-hops are
recognized and safely replaced with the generated path behavior.
M82/M83 extrusion mode changes and G92 E resets are understood. XY arcs using
relative I/J centers are supported; R arcs and other planes are refused.
Unsupported commands show their exact text and line number, with Copy error.
The supplied test slice was inspected: at Z 7.08000 mm, sparse infill inside the
ring separates the two bridge regions but does not touch the annulus. All three
patterns validate as one 932-spoke circular pass with that infill retained.

The combined selection must form one full narrow ring. Cutouts, unrelated
objects, Z hops inside a replacement section, extrusion wipes, unbalanced
retractions, tool/conditional boundaries and inconsistent flow are refused.
Outer radius / inner radius must be <= 1.5. Automatic estimates are suggestions;
geometry validation must pass before export. Both ends of every spoke must
land on supported material. The app does not verify the supporting layer.
Preview diagrams omit travel. Radial spacing grows toward the outer edge.
At the detected source width, each bridge line retains the sliced extrusion rate.
Connected Zigzag turns add the small amount of filament required for their actual
path length. Changing bridge width scales bridge extrusion proportionally; the
preview reports the exact flow percentage. No Z hop is inserted in Zigzag mode.
Bridge speed never exceeds the original slowest bridge speed. Retraction
defaults to zero; adjust for your printer if desired.

FILES AND UNINSTALL
Settings, saved hook profiles, errors and hook backups are in
%LOCALAPPDATA%\Radial Bridges. Hook mode keeps an exact original G-code backup
there before rewriting Studio's temporary file. Backups are not auto-deleted.
Uninstall through Windows Settings > Apps, or the Start menu shortcut. Your
profiles and backups are retained. Remove the hook from Studio before
uninstalling. You may delete that data folder yourself when no longer needed.

VALIDATION STATUS
Cursor-anchored zoom, drag pan, Fit/reset, safe same-layer feature reordering,
three bridge patterns, connected Zigzag turns without repeated wipe retractions,
width/flow calibration sweeps, Bambu wipe/Z-hop recognition,
generic safe M-code preservation, retained intervening features,
split-region grouping, Clear model, selection, command preservation,
XY I/J arcs, exact error messages, state restoration, extrusion conservation, geometry
rejections, 3MF extraction, profile matching, backups and GUI flows were tested
on synthetic G-code. The GUI was rendered and inspected on Linux with Qt.
Windows x64 executables were cross-built and their packaging/dependencies
checked, but Windows execution was blocked in the build environment. The
installer, native Windows launch and actual Bambu interaction have not been
run on a Windows machine here. No physical print validation was performed.
The installer and executable are unsigned.
The Windows launcher embeds the Radial Bridges icon and runs the bundled
interpreter inside the RadialBridges.exe process. The app also sets its Windows
application identity and display name so the taskbar does not show Python.

OPEN SOURCE
Application Python source is installed beside the executable. Launcher source
and installer script are in the accompanying source package. See LICENSE.txt
and THIRD-PARTY-NOTICES.txt. This tool is independent of Bambu Lab.
