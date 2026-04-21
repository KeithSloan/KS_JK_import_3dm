Import Rhinoceros 3D files in Blender
=====================================

This is a fork of [jesterKing/import_3dm](https://github.com/jesterKing/import_3dm)
with added support for importing Rhino surfaces as native Blender NURBS Surface
objects, preserving the exact control point topology rather than importing as
render meshes.

This add-on uses the `rhino3dm.py` module
(https://github.com/mcneel/rhino3dm) to read in 3dm files.

Requirements
============

This add-on works with Blender 4.2 and later.

NURBS Surface Import
====================

When the **As NURBS Surfaces** option is enabled (under BRep in the import
dialog), Brep and Extrusion geometry is imported as Blender `type='SURFACE'`
objects instead of render meshes.

Each Brep face is converted to a group of NURBS splines (one per V-row) in a
Surface data block. The surface is parameterised with clamped-endpoint knots;
Rhino's original chord-length parameterisation is not preserved but the
control point topology is exact.

### Merge Faces option

Controls how multi-face Breps (e.g. a cylinder with lateral surface + end caps)
are handled:

- **Merge Faces** (default, on): all faces with a compatible U control-point
  count are combined into a single Blender SURFACE object. Faces with a
  different U count (e.g. flat end caps on a cylinder) are skipped with a
  warning.
- **Merge Faces off**: each Brep face becomes its own Blender SURFACE object,
  giving a faithful one-to-one mapping suitable for round-trip testing and
  re-export.

### Extrusion objects

Rhino `Extrusion` objects (used for cylinders, boxes, and other prismatic
shapes) are automatically converted to Brep before NURBS import, using the
same face-handling logic as above.

Limitations
-----------

- Trimming curves are not preserved — the full underlying surface is imported
- Non-uniform knot vectors are approximated with clamped/uniform knots
- If a face cannot be converted, it is skipped (or falls back silently to a
  render mesh if no faces convert at all)

Installation
============

On Windows and macOS you need to download the correct ZIP archive from
https://github.com/jesterKing/import_3dm/releases/latest .

1. Download ZIP archive
1. Open Blender preferences
1. Open Add-ons section
1. Click Install... button
1. Select the downloaded ZIP archive
1. Click Install
1. Enable the add-on
</content>
</invoke>