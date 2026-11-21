"""How a camera's motion looks to a viewer, frame by frame, in units that don't depend on the
size of the world: a pan across a desk and a pan across the solar system read the same.

From a camera (position, aim point, lens) sampled per frame (sweep_h and sweep_v are the signed
pan and tilt: turning, plus half of any sideways or vertical travel):
  sweep    how fast the picture sweeps sideways, in frame widths per second: the view's
           rotation plus the parallax of the aim point from sideways travel
  zoom     how fast the picture scales at the aim's depth, in log units per second (positive =
           it grows: a push in or a lens zoom in), from the camera's motion along its view and
           the lens, so handing the aim to a nearer or farther subject isn't read as a zoom
  roll     degrees per second about the view axis
  energy   the overall rate of change of the picture (the length of the three combined)
plus each one's acceleration and jerk. Scene changes (cuts) split the measurement.

No dependencies.
"""

import math

SENSOR_W = 36.0


def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a) or 1e-12
    return [a[0] / n, a[1] / n, a[2] / n]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def hfov(lens):
    return 2 * math.atan(SENSOR_W / (2 * lens))


def angle(a, b):
    c = max(-1.0, min(1.0, dot(unit(a), unit(b))))
    return math.acos(c)


def measure(times, pos, aim, lens, cuts=(), pivot=None):
    """Per-frame kinematics. Returns dict of lists, each len(times): sweep, sweep_h (signed,
    horizontal), sweep_v (signed, vertical), zoom, energy, and their acceleration and jerk
    (suffix _acc, _jerk), plus 'segment' (index of the uncut stretch each frame belongs to).
    `pivot`: the point the camera follows, per frame (the rig's look subject). The camera's travel
    is then measured relative to it, so following a moving subject (a planet along its orbit) at a
    steady distance reads as still, as it looks, not as a zoom or a sideways slide."""
    n = len(times)
    dt = (times[-1] - times[0]) / (n - 1) if n > 1 else 1 / 30
    seg, s = [], 0
    cut_frames = sorted(int(round((c - times[0]) / dt)) for c in cuts)
    for i in range(n):
        while cut_frames and i >= cut_frames[0]:
            cut_frames.pop(0)
            s += 1
        seg.append(s)
    sweep, sh, sv, zoom = [0.0] * n, [0.0] * n, [0.0] * n, [0.0] * n
    up = [0.0, 0.0, 1.0]
    for i in range(n):
        a, b = max(0, i - 1), min(n - 1, i + 1)
        if seg[a] != seg[i]:
            a = i
        if seg[b] != seg[i]:
            b = i
        if a == b:
            continue
        span = (b - a) * dt
        va, vb = sub(aim[a], pos[a]), sub(aim[b], pos[b])
        fw = hfov(lens[i])
        rot = angle(va, vb) / span  # rad/s of the view direction
        # sideways travel relative to the aim distance: parallax of the aim point
        d = norm(sub(aim[i], pos[i])) or 1e-9
        u = unit(sub(aim[i], pos[i]))
        v = [(pos[b][k] - pos[a][k]) / span for k in range(3)]
        if pivot is not None:
            v = [v[k] - (pivot[b][k] - pivot[a][k]) / span for k in range(3)]
        side = [v[k] - dot(v, u) * u[k] for k in range(3)]
        par = norm(side) / d  # rad/s
        # signed horizontal/vertical components of the view rotation
        right = unit(cross(u, up)) if abs(dot(u, up)) < 0.999 else [1.0, 0.0, 0.0]
        upv = cross(right, u)
        dvu = sub(unit(vb), unit(va))
        rh, rv = dot(dvu, right) / span, dot(dvu, upv) / span
        # travelling sideways slides the picture the same way as turning: count it at half weight,
        # as the total sweep does, so a camera trucking left and right is seen changing direction
        ph, pv = dot(v, right) / d, dot(v, upv) / d
        sh[i], sv[i] = (rh + 0.5 * ph) / fw, (rv + 0.5 * pv) / fw
        # zoom: how fast the picture scales at the aim's depth: the camera's speed along its view
        # over that depth, plus the lens change. From the camera's own motion, so handing the aim
        # to a nearer or farther subject (the aim point jumping in depth) isn't read as a zoom.
        fwd = v[0] * u[0] + v[1] * u[1] + v[2] * u[2]
        zoom[i] = fwd / d + (math.log(max(1e-9, lens[b])) - math.log(max(1e-9, lens[a]))) / span
        sweep[i] = math.hypot(rot / fw, par / fw * 0.5)  # parallax counts half: the background moves less than the subject
    energy = [math.sqrt(sweep[i] ** 2 + zoom[i] ** 2) for i in range(n)]
    out = {"t": list(times), "sweep": sweep, "sweep_h": sh, "sweep_v": sv, "zoom": zoom, "energy": energy, "segment": seg}
    for k in ("sweep", "zoom", "energy"):
        acc = deriv(out[k], dt, seg)
        out[k + "_acc"] = acc
        out[k + "_jerk"] = deriv(acc, dt, seg)
    return out


def deriv(ys, dt, seg):
    n = len(ys)
    out = [0.0] * n
    for i in range(n):
        a, b = max(0, i - 1), min(n - 1, i + 1)
        if seg[a] != seg[i]:
            a = i
        if seg[b] != seg[i]:
            b = i
        if a != b:
            out[i] = (ys[b] - ys[a]) / ((b - a) * dt)
    return out


def screen(pos, aim, lens, point, aspect=16 / 9):
    """Where a world point lands on screen, as (x, y) in frames from the centre (-0.5..0.5
    across), and its depth. None if behind the camera."""
    f = unit(sub(aim, pos))
    up = [0.0, 0.0, 1.0]
    right = unit(cross(f, up)) if abs(dot(f, up)) < 0.999 else [1.0, 0.0, 0.0]
    upv = cross(right, f)
    d = sub(point, pos)
    z = dot(d, f)
    if z <= 1e-9:
        return None
    half = math.tan(hfov(lens) / 2)
    x = dot(d, right) / (z * half) / 2
    y = dot(d, upv) / (z * half / aspect) / 2
    return x, y, z
