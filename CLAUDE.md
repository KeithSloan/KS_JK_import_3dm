# Claude Code Instructions — KS_JK_import_3dm

## Overview

This is a fork of [jesterKing/import_3dm](https://github.com/jesterKing/import_3dm).
Key additions over upstream:

- NURBS Surface import (`ObjectType.Surface` dispatch in `converters/__init__.py`)
- Custom properties on imported Curve data blocks to enable correct roundtrip
  with [Blender_Export_3DM](https://github.com/KeithSloan/Blender_Export_3DM)
- Distinct `bl_idname = "ks_jk_import_3dm.some_data"` so both importers can
  coexist in the same Blender session for side-by-side comparison testing

## Blender installation convention

After installing Blender, the user renames `/Applications/Blender.app` to
`/Applications/Blender_x.y.z.app` (e.g. `/Applications/Blender_5.1.1.app`).
Always use the versioned path in shell commands.

## Deployment

This extension is deployed as a **copy** (not a symlink) to both Blender versions:

```
~/Library/Application Support/Blender/4.4/extensions/user_default/ks_jk_import_3dm/
~/Library/Application Support/Blender/5.1/extensions/user_default/ks_jk_import_3dm/
```

After editing any source file, copy it to both locations.  Delete any `.pyc`
cache files for the changed module to force recompilation:

```bash
cp import_3dm/converters/nurbs_surface.py \
   ~/Library/Application\ Support/Blender/5.1/extensions/user_default/ks_jk_import_3dm/converters/nurbs_surface.py
rm -f ~/Library/Application\ Support/Blender/5.1/extensions/user_default/ks_jk_import_3dm/converters/__pycache__/nurbs_surface.cpython-313.pyc
```

## Blender NURBS surface — Python API limitation

Blender 5.x stores NURBS surfaces natively as a **single spline** with all
`count_u × count_v` control points, with the U dimension in the internal field
`pntsu` (exposed as the read-only `point_count_u` property).  This allows
`order_v` and cyclic flags to be stored correctly.

The Python API **cannot** create this format: `point_count_u` / `pntsu` is
`PROP_NOT_EDITABLE`.  The only path from Python is **multi-spline** format (one
spline per V-row), in which Blender clamps `order_v` to 2 on each individual
spline (since each row has `pntsv = 1`).  Cyclic flags may also be unreliable
in multi-spline layout on Blender 5.x.

**Workaround:** the true rhino values are stored as custom properties on the
Curve data block in `converters/nurbs_surface.py`:

| Property | Meaning |
|---|---|
| `rhino_order_u` | NURBS order in U |
| `rhino_order_v` | NURBS order in V (Blender clamps this to 2 in multi-spline format) |
| `rhino_cyclic_u` | 1 if surface is closed in U, else 0 |
| `rhino_cyclic_v` | 1 if surface is closed in V, else 0 |

The paired exporter (`export_nurbs_3dm.py` in Blender_Export_3DM) reads these
properties when it detects multi-spline format, ensuring a correct roundtrip.

## Test suite

Round-trip tests are run from the
[Blender_Export_3DM](https://github.com/KeithSloan/Blender_Export_3DM) repo:

```bash
# .blend → export → import → re-export → compare (KS_JK only)
/Applications/Blender_5.1.1.app/Contents/MacOS/Blender --background \
    --python utilities/batch_blend_compare.py -- \
    --input  SampleBlendFiles/V5.1.1 \
    --output /tmp/blend_compare

# Side-by-side JK vs KS comparison
/Applications/Blender_5.1.1.app/Contents/MacOS/Blender --background \
    --python utilities/batch_compare_importers.py -- \
    --input  SampleBlendFiles/V5.1.1 \
    --output /tmp/compare_out
```

### Current results (Blender 5.1.1)

| File | KS result |
|------|-----------|
| BezierCurve | EQUIVALENT |
| NurbsCurve | GEOMETRY OK |
| SurfCircle_ | GEOMETRY OK |
| SurfCylinder | GEOMETRY OK |
| SurfPatch | GEOMETRY OK |
| SurfSphere | EQUIVALENT |
| SurfTor_us | GEOMETRY OK |
| SurfTorus | GEOMETRY OK |
