"""Export subject shapes from real meshes: points on a model's surface, in the model's own frame,
for framing and composition checks (cine/core/shape.py). Run once per model, inside Blender.

    from cine.blender import hull
    pts = hull.points(objs, n=300, region=((0, 0, 0.9), 2.3))   # vertices near the bus and dish
    hull.save({"voyager": pts, "dish": hull.points([dish_obj])}, "assets/shapes/voyager.json")

Points are the evaluated mesh's vertices in world space (import the model at the identity, so
world space is the model's frame), optionally kept to a sphere `region`, then thinned to `n` by
farthest-point sampling, which keeps the extremes that decide framing. GPL-3.0-or-later.
"""

import json

import numpy as np


def points(objects, n=300, region=None):
    import bpy

    dg = bpy.context.evaluated_depsgraph_get()
    chunks = []
    for o in objects:
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        M = np.array(o.matrix_world)
        chunks.append(co @ M[:3, :3].T + M[:3, 3])
        ev.to_mesh_clear()
    if not chunks:
        return []
    P = np.concatenate(chunks)
    if region is not None:
        c, r = np.array(region[0], float), float(region[1])
        P = P[np.linalg.norm(P - c, axis=1) <= r]
    return thin(P, n)


def thin(P, n):
    """Farthest-point sampling: n points spread over the cloud, extremes first."""
    P = np.asarray(P, float)
    if len(P) <= n:
        return P.round(4).tolist()
    c = P.mean(axis=0)
    idx = [int(np.argmax(np.linalg.norm(P - c, axis=1)))]
    d = np.linalg.norm(P - P[idx[0]], axis=1)
    for _ in range(n - 1):
        i = int(np.argmax(d))
        idx.append(i)
        d = np.minimum(d, np.linalg.norm(P - P[i], axis=1))
    return P[idx].round(4).tolist()


def save(shapes, path):
    with open(path, "w") as f:
        json.dump(shapes, f, separators=(",", ":"))
