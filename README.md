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
dialog), Brep geometry is imported as Blender `type='SURFACE'` objects instead
of render meshes.

Each Brep face is converted to a group of NURBS splines (one per V-row) in a
single Surface data block. The surface is parameterised with clamped-endpoint
knots; Rhino's original chord-length parameterisation is not preserved but the
control point topology is exact.

Limitations:

- Trimming curves are not preserved — the full underlying surface is imported
- Non-uniform knot vectors are approximated with clamped uniform knots
- If a face cannot be converted, it falls back silently to a render mesh

Installation
============

On Windows and MacOS you need to download the correct ZIP archive from
https://github.com/jesterKing/import_3dm/releases/latest .

1. Download ZIP archive
1. Open Blender preferences
1. Open Add-ons section
1. Click Install... button
1. Select the downloaded ZIP archive
1. Click Install
1. Enable the add-on
