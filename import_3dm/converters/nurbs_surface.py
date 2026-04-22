# MIT License
#
# Copyright (c) 2024 Keith Sloan
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
nurbs_surface.py — Import Rhino Brep surfaces as Blender NURBS Surface objects.

Blender represents a NURBS surface as a collection of splines inside a
type='SURFACE' curve data block: one spline per V-row, each containing
count_u control points.  The V direction is implicit in the spline arrangement;
order_v / use_cyclic_v on each spline controls inter-row interpolation.

Face handling
-------------
When merge_brep_faces=True (default): all faces are combined into a single data
block, provided they share the same U control-point count.  Faces with an
incompatible U count (e.g. end caps on a cylinder) are skipped with a warning.

When merge_brep_faces=False: each Brep face becomes its own type='SURFACE' data
block; import_nurbs_surface returns a list of data blocks and the caller
(convert_object) creates one Blender object per item in the list.

Limitations
-----------
- Trimming curves are not preserved; the full underlying surface is imported.
- Blender NURBS uses clamped-endpoint or uniform knots only; non-uniform knot
  spacing from Rhino is not reproduced exactly.
- If no faces convert, returns None so the caller falls back to a render mesh.
"""

import bpy


def _face_to_nurbs(face):
    """Extract a rhino3dm NurbsSurface from a BrepFace, or None on failure."""
    try:
        srf = face.UnderlyingSurface()
        if srf is None:
            return None
        return srf.ToNurbsSurface()
    except Exception as e:
        print(f"[nurbs_surface] Face conversion error: {e}")
        return None


def _add_nurbs_spline(surf_data, ns, scale):
    """
    Add NURBS control points to *surf_data* for one NurbsSurface (*ns*).

    Blender NURBS surface format — Python API limitation
    -----------------------------------------------------
    Blender 5.x stores NURBS surfaces internally as a *single* spline containing
    all count_u × count_v control points, with the U dimension recorded in the
    internal field ``pntsu`` (exposed as the read-only ``point_count_u`` property).
    This allows ``order_v`` to be set correctly (up to count_v) and cyclic flags
    to be stored reliably on the combined surface.

    The Python API provides no way to set ``point_count_u`` / ``pntsu`` directly
    (it is flagged PROP_NOT_EDITABLE in Blender's RNA).  The only available path
    from Python is the *multi-spline* format: one spline per V-row, each containing
    count_u points.

    Consequence: in multi-spline format Blender clamps ``order_v`` to 2 on every
    individual spline (because each spline has pntsv=1, so the maximum meaningful
    V-order for that spline is 1, floored to the minimum of 2).  Similarly,
    ``use_cyclic_u`` / ``use_cyclic_v`` may not survive a save/reload cycle in
    multi-spline layout on Blender 5.x.

    Workaround: the true rhino values are stored as custom properties on the
    Curve data block (``rhino_order_u``, ``rhino_order_v``, ``rhino_cyclic_u``,
    ``rhino_cyclic_v``).  The exporter (export_nurbs_3dm.py) reads these when it
    detects multi-spline format, allowing a correct roundtrip even though Blender
    itself cannot represent the values natively from Python.

    Returns True on success, False if the surface is degenerate.
    """
    count_u = ns.Points.CountU
    count_v = ns.Points.CountV

    if count_u < 2 or count_v < 2:
        print(f"[nurbs_surface] Degenerate surface skipped ({count_u}x{count_v} pts)")
        return False

    is_rational = getattr(ns, 'IsRational', False)

    try:
        closed_u = ns.IsClosed(0)
        closed_v = ns.IsClosed(1)
    except Exception:
        closed_u = False
        closed_v = False

    order_u = min(max(ns.OrderU, 2), count_u)
    order_v = min(max(ns.OrderV, 2), count_v)

    for j in range(count_v):
        spline = surf_data.splines.new('NURBS')
        spline.points.add(count_u - 1)  # new() already adds 1 point

        for i in range(count_u):
            cp = ns.Points.GetControlPoint(i, j)  # returns Point4d directly
            w = cp.W
            if is_rational and w and w != 0.0:
                spline.points[i].co = (
                    cp.X / w * scale,
                    cp.Y / w * scale,
                    cp.Z / w * scale,
                    w,
                )
            else:
                spline.points[i].co = (
                    cp.X * scale,
                    cp.Y * scale,
                    cp.Z * scale,
                    1.0,
                )

        spline.order_u = order_u
        spline.order_v = order_v
        spline.use_cyclic_u = closed_u
        spline.use_cyclic_v = closed_v
        spline.use_endpoint_u = not closed_u
        spline.use_endpoint_v = not closed_v

    # Store rhino NURBS properties as custom data on the surface block.
    # Blender's multi-spline format clamps order_v to 2 and may lose cyclic flags,
    # so the exporter reads these values back to ensure correct roundtrip.
    surf_data["rhino_order_u"] = order_u
    surf_data["rhino_order_v"] = order_v
    surf_data["rhino_cyclic_u"] = 1 if closed_u else 0
    surf_data["rhino_cyclic_v"] = 1 if closed_v else 0

    return True


def _make_surf_data(context, face_name, ns, scale):
    """Create a single type='SURFACE' data block for one NurbsSurface."""
    surf_data = context.blend_data.curves.new(face_name, 'SURFACE')
    surf_data.dimensions = '3D'
    if _add_nurbs_spline(surf_data, ns, scale):
        return surf_data
    bpy.data.curves.remove(surf_data)
    return None


def import_nurbs_surface(context, ob, name, scale, options):
    """
    Import a Brep geometry object as one or more Blender NURBS Surface data blocks.

    Returns:
      - A list of surf_data objects (one per face) when merge_brep_faces=False.
      - A single surf_data when merge_brep_faces=True.
      - None if no faces could be converted (caller falls back to render mesh).
    """
    og = ob.Geometry
    merge = options.get("merge_brep_faces", True)
    n_faces = len(og.Faces)

    if merge:
        # Legacy merged mode: all compatible faces into one data block
        surf_data = context.blend_data.curves.new(name, 'SURFACE')
        surf_data.dimensions = '3D'
        converted = 0
        failed = 0
        expected_count_u = None

        for fi in range(n_faces):
            face = og.Faces[fi]
            if isinstance(face, list):
                failed += 1
                continue
            ns = _face_to_nurbs(face)
            if ns is None:
                print(f"[nurbs_surface] '{name}' face {fi}: could not obtain NurbsSurface")
                failed += 1
                continue
            if expected_count_u is None:
                expected_count_u = ns.Points.CountU
            elif ns.Points.CountU != expected_count_u:
                print(f"[nurbs_surface] '{name}' face {fi}: U count {ns.Points.CountU} != {expected_count_u}, skipped (incompatible cap/face)")
                failed += 1
                continue
            if _add_nurbs_spline(surf_data, ns, scale):
                converted += 1
            else:
                failed += 1

        if converted == 0:
            bpy.data.curves.remove(surf_data)
            print(f"[nurbs_surface] '{name}': no faces converted, falling back to render mesh")
            return None
        if failed > 0:
            print(f"[nurbs_surface] '{name}': {converted}/{n_faces} face(s) merged ({failed} skipped)")
        else:
            print(f"[nurbs_surface] '{name}': {converted} face(s) merged")
        return surf_data

    else:
        # Default separate mode: one data block per face
        results = []
        for fi in range(n_faces):
            face = og.Faces[fi]
            if isinstance(face, list):
                continue
            ns = _face_to_nurbs(face)
            if ns is None:
                print(f"[nurbs_surface] '{name}' face {fi}: could not obtain NurbsSurface")
                continue
            face_name = f"{name}_f{fi}" if n_faces > 1 else name
            sd = _make_surf_data(context, face_name, ns, scale)
            if sd is not None:
                results.append(sd)

        if not results:
            print(f"[nurbs_surface] '{name}': no faces converted, falling back to render mesh")
            return None

        print(f"[nurbs_surface] '{name}': {len(results)}/{n_faces} face(s) as separate surfaces")
        return results
