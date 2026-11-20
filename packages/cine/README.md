# cine

Scene-level 3D direction for explainer video: smooth camera and actor motion by construction, and instruments that show a whole animation at once, so problems are found before anyone watches a render.

Status: in progress. Built so far:
- the curve model, kinematics and flags
- the motion sheet, the director's map and the scene viewer
- the camera rig
- the Blender layer: baking curves into keyframes, and an EEVEE preview with motion blur and bloom

## The idea

**Animation is curves.** Every animated quantity in a scene (camera position, aim point, lens, an actor's position, rotation, scale, glow) is a named curve of time, held in one motion file (`*.motion.json`). Blender is baked from it, the views draw it, QA measures it.

**See it all at once.** `python3 -m cine.see scene.motion.json --png` writes:
- **The motion sheet:** every curve on one time axis under the narration's words. It shows:
  - camera travel, with a dot per frame (the spacing shows speed)
  - view direction and subject scale
  - sweep and zoom speed, with the reference range shaded
  - acceleration, flags, actor curves and composition
- **The director's map:** the camera's path from above and from the side. It's coloured by time, with a frustum and timestamp every second.
- **The scene viewer** (`.html`): both, plus the preview video, on one scrubber. Drag it, and a cursor moves along every curve, a glyph moves along the camera path, and the video seeks to the same frame.

**Flags** (`cine.core.qa`), in units that don't depend on the size of the world:
- **hiccup:** stop-start between moves
- **reversal:** a pan, tilt or zoom that snaps back the other way (the rate crosses zero steeply). Easing from a push into a pull is fine.
- **jerk:** a lurch
- **fast:** sweep or zoom beyond the reference range
- **dead:** stillness too long
- **jump:** a hidden cut

The thresholds are provisional until `calibrate` measures reference footage.

## The camera

A scene's camera journey is a handful of poses at times, and the camera travels through them on minimum-jerk curves: the path a skilled hand takes through via points.

```python
from cine.camera.rig import Rig
rig = Rig({"voyager": craft, "thrusters": cluster}, fps=30)
rig.key(0,  look="voyager",   dist=30, az=140, el=6, lens=40, screen=(-1/6, 0))
rig.key(9,  look="thrusters", dist=4,  az=80,  el=28, screen=(0, 0))   # push in, hand the aim over
rig.key(20, look="voyager",   dist=14, az=20,  el=-5, lens=35)        # round and back out
cam = rig.sample(0, 20)
```

**A key is where the camera is, relative to what it looks at:**
- distance, bearing (`az`, `el`) and lens
- where the subject sits on screen
- a subject, or weights over several for group framing

Anything left out carries over from the key before. So the vocabulary of moves (push in, pull back, orbit, crane, rack the lens, hand the aim to a new subject) is just keys.

**How the curves are built:**
- **Bearing and log-distance** use the minimum-jerk spline. It's continuous to the fourth derivative, and at rest only at the ends or at a key marked `stop`.
- **Lens, look weights and screen offsets** use monotone quintics. A zoom never overshoots, and the aim never swings past a subject.

The keys are stored as curves in the motion file, and the sheet draws them as an animator's graph editor does, with a diamond at each key.

`frame_two()` solves the bearing that puts two subjects at chosen screen positions.

## Layout

| Path | What |
|---|---|
| `cine/core/ease.py` | Easing: minimum-jerk, S-curve, springs, CSS cubic-bezier |
| `cine/core/curve.py` | `Curve` and `Motion`, the motion file. A curve is keys (minimum-jerk, monotone, spline, eased, linear or hold interpolation) or per-frame samples |
| `cine/core/path.py` | Centripetal Catmull-Rom paths with arc length, and zero-phase smoothing |
| `cine/camera/rig.py` | The camera rig: keyed poses, minimum-jerk travel, exact screen composition, two-subject framing |
| `cine/blender/bake.py` | Bakes a motion file into Blender: a camera and any property, keyed every frame |
| `cine/blender/look.py` | The preview look: EEVEE with motion blur, AgX colour, compositor bloom, a lighting rig from the true light source, emissive and plume materials |
| `cine/core/kinematics.py` | What a viewer sees: sweep, zoom and roll rates, with acceleration and jerk |
| `cine/core/qa.py` | Flags |
| `cine/viz/` | The sheet, the map, the viewer, and SVG to PNG (headless Chrome, or ImageMagick) |
| `cine/see.py` | The command |
| `test/cine.test.ts` | Tests (vitest runs the pure-Python core with `python3`) |

`cine/core` and `cine/camera` are pure Python with no dependencies. `cine/blender` runs inside Blender and is GPL-3.0-or-later, as Blender's API requires; the rest is Apache-2.0.
