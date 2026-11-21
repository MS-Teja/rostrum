# cine

Scene-level 3D direction for explainer video: smooth camera and actor motion by construction, and instruments that show a whole animation at once, so problems are found before anyone watches a render.

Status: in progress. Built so far:
- the curve model, kinematics and flags
- the motion sheet, the director's map and the scene viewer
- the camera rig
- the Blender layer: baking curves into keyframes, and an EEVEE preview with motion blur and bloom
- calibration on real footage, and the film profile
- the crew: four craft guides, shots set up from intent, composition and exposure checks, and the dailies

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

The thresholds come from a profile measured on real footage (below). Without one, provisional defaults apply.

## Calibration

`cine.calibrate` reads films the way cine reads its own cameras:
1. It streams each film small and grey through ffmpeg and finds the cuts.
2. Between every pair of frames it measures the picture's pan, tilt and zoom, using phase correlation on a 3×3 block grid with a robust fit.
3. It writes percentiles over every moving frame as a profile: flag thresholds, plus the reference band shaded on the sheet.

```bash
python -m cine.calibrate film1.mp4 film2.mkv --out profiles/film.json --name film   # needs numpy and ffmpeg
python -m cine.see scene.motion.json --profile profiles/film.json --png
```

`profiles/film.json` comes from four Blender open films, all CC BY: *Big Buck Bunny* (2008), and *Caminandes 1: Llama Drama*, *Caminandes 2: Gran Dillama* and *Caminandes 3: Llamigos* (2013–16). That's 173 shots, 14.5 minutes. Copyright Blender Foundation.

What the films set:

| Measure | Value |
|---|---|
| Pan or tilt, fast end (99th percentile) | 0.70 frame widths per second |
| Zoom, fast end (99th percentile) | 0.39 log-scale per second |
| Turn-backs, steep end (95th percentile) | 0.51 per second² |

Jerk and the stop-start shape keep cine's defaults: measured from footage, they are dominated by measurement noise.

`profiles/nasa-svs.json` is a reference, not a standard. It comes from seven public-domain NASA Goddard visualizations (8 shots). NASA's animations move more slowly than the films: their fast zoom is 0.31 per second and their fast pan 0.30 frame widths per second. The explainer standard has to come from the creators whose pace we want.

**Sanity check:** read with the film profile, the rejected Voyager previs raises 23–39 flags per scene, and reel scene A raises none.

`--check render.mp4` reads a render the same way. It's for footage and textured scenes: on a sparse star field, the block fit misreads zoom. For a cine scene, the curve-based QA is the truth, since it knows the camera exactly.

## The crew

The jobs of a film crew, folded into four roles as on a small production. Each has a written guide in `crew/`, with the craft as numbers where it can, plus tools and automatic checks.

**Building a scene follows `crew/build.md`:** eight gates in order (paper, references, hero proof, set and light, blocking, actors, dailies, render). Each leaves evidence in the scene's `notes.md`, and the owner approves three of them: the paper plan, the look and the final render. New scenes start from `templates/scene.py` and `templates/notes.md`.

| Role | Guide | Tools and checks |
|---|---|---|
| Director (folds in editor, continuity) | `crew/director.md`: the brief, pacing, transitions, continuity, the standing rules | the brief in the motion file; moves against words |
| Cinematographer | `crew/cinematographer.md`: shot sizes, angles, lenses, motives, composition, the 180° line | `camera/shot.py` sets up a shot from intent; `core/compose.py` checks size, edges, dominance, lead room and headroom on held frames |
| Look (folds in gaffer, production designer, colorist) | `crew/look.md`: motivated light, exposure targets, real assets, the grade | `blender/look.py` (lights, starfield, plume, bloom); `core/look.py` checks exposure, contrast, crush and form per still, by the shot's planned look |
| Animator | `crew/animator.md`: the principles applied to objects, one dominant motion, truth in motion | `blender/actors.py` presets (gas puffs, glows, pulses); `core/actors.py` flags an actor out of frame or too small, and the dailies flag one hidden behind something; `core/text.py` flags on-screen text that moves, ticks or flashes |

**Dailies:** `cine.dailies` renders a scene's key poses and the midpoints between them in about 15 s. It packs:
- a contact sheet with overlays
- every check's report
- the brief and the shot plan
- the sheet and the map

**The reviewer:** one independent, read-only agent reviews the pack against the four guides before anyone else sees it. Every note is answered in the scene's notes, fixed or declined with a reason.

```python
from cine.camera.shot import Framer
F = Framer(rig, {"voyager": voyager_points, "thrusters": cluster_points}, facing={"voyager": dish_axis})
F.shot(0.0, "voyager", "medium wide", angle=-10, side="left third", lens=30, az=110, motive="establish")
F.shot(9.4, "thrusters", 0.8, angle=20, side="centre", lens=50, az=74, motive="emphasise", look="low-key")
```

## The voice

The voiceover drives the picture (`cine/core/voice.py`):
- **Keys by words.** `voice.at("fire")` gives the time a word starts, and `edge="end"` the time it ends. Camera keys, actor cues and puffs are placed by words, not seconds.
- **Pace from the voice.** The pace combines the speaking rate (against the take's own median), the loudness when the audio is given, and pauses. It runs from about 0.6 for a slow, quiet line to 1.5 for a fast, loud one.
- **Limits follow the pace.** The speed limits scale with it moment by moment (`qa.flags(scale=...)`), so a brisk move fits a brisk line and a slow line asks for calm. The sheet shows the pace under the words.
- **Still or slow under the voice.** While the voice explains, the camera holds (`F.hold(t)`) or creeps slowly one way (`creep=`, `drift=`). The checks flag what's actually unnecessary:
  - **wander:** changing direction twice or more in 3 s;
  - **fidget:** a small, short move between holds.

  A deliberate hold of 1.2 s or more isn't a stop-start, and stillness while someone is speaking isn't a dead scene.

## Across scales

`cine/blender/scale.py` handles scenes that span many orders of magnitude, such as a spacecraft, then the solar system, then the nearest stars:
- **The stage.** Everything lives in true units under one root. Each frame, the root is scaled so the camera sits 10 units from its aim, so a million-AU scene is float-safe, with the true perspective.
- **Lines** are a constant width on screen at every point, even where they pass the camera. Geometry Nodes sets each point's radius from its distance to the camera. A line can be drawn partway (`reveal`).
- **Dots** keep a minimum pixel size, and **labels** face the camera at a fixed pixel height.
- **Text stays put.** A label takes one place when it appears and holds it until it leaves, fading in and out at a constant size. With `avoid=True`, the place round its anchor is chosen once per appearance, the one clearest of the lines, dots and labels over the whole appearance. `caption_place` picks one screen corner for captions (a date, a readout) for the whole scene. `stage.text_flags()` (`core/text.py`) flags text that is brief, moving, re-placed, ticking, flashing or crowded. The rule comes from an owner's note on a render whose labels dodged lines and ticked every frame: "Texts are constantly changing, they should be at a constant place."
- **The planets' plane** (`plane`): a faint sheet whose grid spacing follows the view, so it reads as a flat surface at every scale.
- **A clock that follows the scale** (`core/clock.py`): calendar time runs in proportion to the view's width, so a craft's on-screen pace stays true at every zoom. Each plateau is solved so a pinned date lands on its word.
- **Real bodies** (`blender/bodies.py`): a banded, ringed planet from a band strip and a measured ring profile, and a sphere that lights itself from the Sun's true direction wherever it is.
- **Zoom-throughs.** A key whose motive is `"zoom-through"` hands the aim across scales in proportion to the view, so the subjects at both scales slide smoothly instead of being flung. Its zoom limit lifts to about one power of ten per 0.8 s, still scaled by the voice.

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
- **Every channel, by default,** uses monotone quintics (pass `Rig(interp="minjerk")` for the older minimum-jerk bearing):
  - a framing never overshoots its key: a push arrives instead of sailing past and back;
  - a move from rest to rest glides like a dolly grip's (ease in, cruise, ease out);
  - the aim never swings past a subject.
- **A key's `handover`** sets when the aim changes subject.

The keys are stored as curves in the motion file, and the sheet draws them as an animator's graph editor does, with a diamond at each key.

`frame_two()` solves the bearing that puts two subjects at chosen screen positions.

## Layout

| Path | What |
|---|---|
| `cine/core/ease.py` | Easing: minimum-jerk, S-curve, springs, CSS cubic-bezier |
| `cine/core/curve.py` | `Curve` and `Motion`, the motion file. A curve is keys (minimum-jerk, monotone, spline, eased, linear or hold interpolation) or per-frame samples |
| `cine/core/path.py` | Centripetal Catmull-Rom paths with arc length, zero-phase smoothing, and actor tracks (`along`, `track`) |
| `cine/core/actors.py` | Actor visibility: out of frame, too small (the dailies add hidden) |
| `cine/blender/actors.py` | Actor presets: gas puffs, glows, appear, pulses along a path |
| `cine/transition.py` | Transitions between scenes, the join (audio laid out, never crossfaded; refuses voice under a transition), and `mux` (frames plus a take at its in-handle) |
| `cine/camera/rig.py` | The camera rig: keyed poses, minimum-jerk travel, exact screen composition, two-subject framing |
| `cine/camera/shot.py` | Shots set up from intent (size, angle, side, lens, view), solved against the subject's real shape |
| `cine/core/shape.py`, `compose.py` | Subject shapes, and composition measured and checked every frame |
| `cine/core/look.py` | Exposure checks by planned look |
| `cine/core/voice.py` | The voiceover: word times, the pace curve, the words lane |
| `cine/blender/hull.py` | Exports subject shapes from real meshes |
| `cine/blender/scale.py` | The scale stage: float-safe scenes across orders of magnitude, constant-width lines, dots, rings, the plane sheet, labels that hold their place, and caption placement |
| `cine/core/text.py` | The text check: brief, moving, re-placed, ticking, flash, busy |
| `cine/core/clock.py` | A clock that follows the scale, with pinned dates solved onto their words |
| `cine/blender/bodies.py` | Planets from real maps: a ringed, banded planet; a self-lit sphere; a sun lamp along a moving direction |
| `cine/blender/nodes.py` | Helpers for shader node trees in code |
| `cine/blender/dailies.py`, `cine/dailies.py` | Key-pose stills, masks, look measures, occlusion, and the dailies pack |
| `crew/` | How to build a scene (`build.md`), and the four craft guides |
| `templates/` | A new scene's starting files: `scene.py` and `notes.md` |
| `cine/blender/bake.py` | Bakes a motion file into Blender: a camera and any property, keyed every frame |
| `cine/blender/look.py` | The preview look: EEVEE with motion blur, AgX colour, compositor bloom, a lighting rig from the true light source, emissive and plume materials |
| `cine/core/kinematics.py` | What a viewer sees: sweep, zoom and roll rates, with acceleration and jerk |
| `cine/core/qa.py` | Flags |
| `cine/viz/` | The sheet, the map, the viewer, and SVG to PNG (headless Chrome, or ImageMagick) |
| `cine/see.py` | The command |
| `cine/frameqa.py` | Frame QA on the rendered video: pops and flicker, from per-frame brightness |
| `cine/calibrate.py` | Measures reference footage into a profile (needs numpy and ffmpeg) |
| `profiles/film.json` | The profile measured from Blender's open films |
| `test/cine.test.ts` | Tests (vitest runs the pure-Python core with `python3`) |

`cine/core` and `cine/camera` are pure Python with no dependencies. `cine/blender` runs inside Blender and is GPL-3.0-or-later, as Blender's API requires; the rest is Apache-2.0.
