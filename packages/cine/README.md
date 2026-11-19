# cine

Scene-level 3D direction for explainer video: smooth camera and actor motion by construction, and instruments that show a whole animation at once, so problems are found before anyone watches a render.

Status: in progress. Built so far: the curve model, kinematics and flags, the motion sheet, the director's map and the scene viewer.

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
- **reversal:** a pan or zoom that turns back within a second
- **jerk:** a lurch
- **fast:** sweep or zoom beyond the reference range
- **dead:** stillness too long
- **jump:** a hidden cut

The thresholds are provisional until `calibrate` measures reference footage.

## Layout

| Path | What |
|---|---|
| `cine/core/ease.py` | Easing: minimum-jerk, S-curve, springs, CSS cubic-bezier |
| `cine/core/curve.py` | `Curve` (keys with spline, eased, linear or hold interpolation, or per-frame samples) and `Motion`, the motion file |
| `cine/core/kinematics.py` | What a viewer sees: sweep, zoom and roll rates, with acceleration and jerk |
| `cine/core/qa.py` | Flags |
| `cine/viz/` | The sheet, the map, the viewer, and SVG to PNG (headless Chrome, or ImageMagick) |
| `cine/see.py` | The command |
| `test/cine.test.ts` | Tests (vitest runs the pure-Python core with `python3`) |

`cine/core` is pure Python with no dependencies. The Blender layer, when it lands, is GPL-3.0-or-later like `stage3d`; the rest is Apache-2.0.
