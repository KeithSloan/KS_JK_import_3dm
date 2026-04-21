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

Limitations
-----------
- Trimming curves are not preserved; the full underlying surface is imported.
- Blender NURBS uses clamped-endpoint or uniform knots only; non-uniform knot
  spacing from Rhino is not reproduced exactly.
- Multi-face Breps: each face becomes a group of V-row splines in the same
  Surface data block.  If no faces convert, falls back to render mesh.
"""

import bpy


def _face_to_nurbs(face):
    """
    Extract a rhino3dm NurbsSurface from a BrepFace.
    Returns the NurbsSurface or None on failure.
    """
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
    Add NURBS splines to *surf_data* for one NurbsSurface (*ns*).

    One spline is created per V-row, each containing count_u control points.
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
        spline.points.add(count_u - 1)  # splines.new() already adds 1 point

        for i in range(count_u):
            # GetControlPoint returns Point4d (X, Y, Z, W) directly
            cp = ns.Points.GetControlPoint(i, j)
            w = cp.W
            if is_rational and w and w != 0.0:
                # Divide homogeneous coords by weight, matching curve.py convention
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

    return True


def import_nurbs_surface(context, ob, name, scale, options):
    """
    Import a Brep geometry object as a Blender NURBS Surface.

    Each Brep face contributes V-row splines to a single type='SURFACE'
    data block.  Returns the data block on success, or None if no faces
    could be converted (caller falls back to render mesh).
    """
    og = ob.Geometry

    surf_data = context.blend_data.curves.new(name, 'SURFACE')
    surf_data.dimensions = '3D'

    converted = 0
    failed = 0
    n_faces = len(og.Faces)

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

        if _add_nurbs_spline(surf_data, ns, scale):
            converted += 1
        else:
            failed += 1

    if converted == 0:
        bpy.data.curves.remove(surf_data)
        print(f"[nurbs_surface] '{name}': no faces converted, falling back to render mesh")
        return None

    if failed > 0:
        print(f"[nurbs_surface] '{name}': {converted}/{n_faces} face(s) converted ({failed} failed)")
    else:
        print(f"[nurbs_surface] '{name}': {converted} face(s) converted")

    return surf_data
