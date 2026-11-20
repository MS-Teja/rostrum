# The cinematographer

The cinematographer decides what the viewer sees, and how it feels, at every moment of a scene:
- where the camera stands
- which lens it uses
- how the frame is composed
- why the camera moves

They work from the director's brief, and hand over a **shot plan**: one line per beat, turned into camera keys with `shot()`.

The numbers below are starting points from film practice, and cine checks the measurable ones automatically. Break a rule only on purpose, and say why in the shot plan.

## 1. Shot size: how big the subject is

Size is measured from the subject's real shape (its hull), not a point. It's the larger of the subject's projected height ÷ frame height and its width ÷ frame width.

| Size | Subject fills | What it's for |
|---|---|---|
| extreme wide | under 0.10 | Scale, isolation, where we are. The subject is a speck in its world. |
| wide | 0.10–0.30 | The whole subject in its surroundings |
| medium wide | 0.30–0.55 | The whole subject, readable, with room around it |
| medium | 0.55–0.80 | The subject owns the frame, with room at the edges |
| close | 0.80–1.10 | The subject fills the frame |
| extreme close | over 1.10 | Cropped on purpose: a detail is now the subject |

**The subject is whatever the beat is about.** When the beat is "the thrusters fire", the subject is the thruster cluster, and the shot is sized on the cluster. The rest of the craft becomes context.

**Context must not take over.** Two limits, both checked:
- **Nearer clutter:** geometry that isn't the subject, and is nearer to the camera than the subject, should cover under 25% of the frame. The exception is a deliberate foreground frame, which must be darker or softer than the subject and must be planned as such.
- **Dominance:** at any depth, no other shape should cover over 35% of the frame *and* more than twice the subject's share.

A "close-up of the thrusters" in which the thruster cluster covers 8% of the frame and the craft around it covers 54% is a shot of the craft. Move in, or use a longer lens, until the subject holds the frame.

**Size changes need room to breathe.** Going from extreme wide to close in one continuous move needs at least 4–5 s at the film profile's zoom limit (0.39 log-scale per second). If the beat is shorter, start the move earlier, or make the change smaller.

## 2. Edge cuts: in or out, never grazing

A subject is either:
- **inside the frame**, with at least a 5% margin to every edge; or
- **cut decisively**, with at least 20% of it outside the frame.

Anything in between reads as a mistake: a silhouette touching the edge, or a sliver cut off.

Thin parts (booms, antennas, cables) may leave the frame. List them as `may_leave` in the subject definition, and they're exempt.

## 3. Placement

- **Thirds.** Place the subject's centre at x = ±1/6 of the frame (the vertical thirds). Centre it (x = 0) only for symmetry, confrontation or a subject coming straight at the camera.
- **Lead room.** Leave the open side of the frame in front of the subject: where it faces, where it moves, or where it sends something (Voyager's beam, a signal). Offset the subject about 1/6 of the frame to the opposite side.
- **Headroom.** In medium and close shots, keep the top of the subject 5–15% below the top of the frame. In wide shots, put the subject or the horizon on a horizontal third.
- **Two subjects.** Put them on opposite thirds (`frame_two()`). Which one is nearer the camera is the one the beat is about.

## 4. Angle

The angle is the camera's elevation relative to the subject (`el` in a key).

| Angle | Elevation | Says |
|---|---|---|
| eye level | −5° to 5° | Neutral. A plain statement. |
| low | −10° to −35° | Power, scale, a hero. Good for machines meant to impress. |
| high | 10° to 35° | Overview, clarity, vulnerability |
| overhead | 60° to 90° | A plan or diagram view: how parts relate |
| tilted horizon | roll | Unease. Avoid unless the story is unease. |

**In space there is no up.** The scene chooses one (cine uses +Z) and keeps it, so the stars and the craft don't seem to swim. Keep the horizon level unless rolling it is the point.

## 5. Lens

Fields of view are horizontal, on cine's 36 mm sensor.

| Focal length | Field of view | Character | Use |
|---|---|---|---|
| 14–20 mm | 104–84° | Huge depth. Near things loom, edges stretch, travel feels fast. | Being inside a space (a server aisle, a cockpit). Dramatic closeness. Use sparingly. |
| 24–28 mm | 74–66° | Wide, with deep space between foreground and background | Establishing a place. Moving through a set. |
| 35 mm | 54° | Natural, slightly wide | The default for a camera moving among objects |
| 50 mm | 40° | Neutral, close to how attention sees | Studying an object. Calm medium shots. |
| 85 mm | 24° | Compressed, isolating, flattering | Close shots of a part. Isolating it from clutter. |
| 135–200 mm | 15–10° | Strong compression: the background looks big and near | Setting a far object against a near one. Observation from a distance. |

**Relative size comes from distance, not the lens.** How big a background object looks next to a foreground one depends only on the ratio of their distances from the camera. To make Earth loom behind Voyager honestly:
1. Move the camera far back, so the two distances get closer to equal.
2. Use a long lens to fill the frame.

That's real compression, not an enlarged prop. Where geometry makes it impossible (from 160 AU, Earth is a point at any focal length), the prop is a cheat, and must be labelled as one.

**A lens also sets how motion feels.**
- On a wide lens, a camera move gives strong parallax and feels fast and physical.
- On a long lens, the same move feels slow and flat.
- A **push-in** (moving the camera) feels emotional and physical.
- A **zoom** (changing the lens) feels observational, documentary.
- A **dolly-zoom** (pushing in while zooming out to hold size) is vertigo. It's a single effect; don't reach for it twice.

**Changing lens:** change it between beats on purpose. Inside a continuous move, change it slowly (cine's lens curve is monotone). A wide lens very close to a subject distorts it: keep 24 mm and wider at least 2–3 subject sizes away, unless the distortion is the point.

## 6. Movement: every move needs a motive

Write the motive for each move in the shot plan:

| Motive | Move |
|---|---|
| **reveal** | Pull back, crane over or orbit round something, to show what was hidden |
| **follow** | Keep a moving subject in frame, trailing it slightly (`look` on it, lead room ahead of it) |
| **emphasise** | Push in as the important thing happens or is said |
| **relate** | Travel from one subject to another to connect them (hand the `look` over) |
| **establish** | A slow drift, so a still scene has depth and isn't dead |

**Arrive before the action.** The camera reaches its framing, or slows near it, 0.5–1 s *before* the key action (the puff, the light switching on, the word that matters), so the viewer's eye is already there. A camera still moving fast when the action happens means the viewer misses it.

**One dominant motion.** When an actor does something important, the camera slows or holds. When the camera makes a big move, actors stay quiet. The sheet's speed rows and the actor rows show whether both peak at once.

**Speeds** (film profile, measured on Blender's open films):
- **Sweep:** under 0.70 frame widths per second at the fast end, and usually 0.01–0.17.
- **Zoom:** under 0.39 log-scale per second.
- **Turn-backs:** a pan, tilt or zoom shouldn't snap back faster than 0.51 per second².

**Parallax makes depth.** Moving sideways relative to the view, past something near, gives the strongest sense of depth. A straight push towards a subject with nothing in front of it gives almost none. Give it foreground, or add some sideways travel.

## 7. Depth and the frame

- **Layers.** Compose foreground, midground and background. Most shots need at least two of them. A frame where everything sits at one depth looks flat.
  - In space: the craft (midground), stars (background), and a part of the craft or a nearer object as foreground.
- **Negative space.** Empty frame is a statement: alone, vast, far. Use it deliberately, with the subject placed on a third, not lost in the middle.
- **Tangents and mergers.** Don't let an edge of the subject just touch another object's edge or the frame's edge. Don't let a thin part seem to grow out of something behind it (an antenna out of Earth). Separate the silhouettes.
- **Light and the camera.** The look role sets the lights; the cinematographer chooses where the camera stands relative to the key light:
  - **Front light** (key within 20° of the lens axis) looks flat.
  - **Side light or three-quarter light** (45–120° from the lens axis) shows shape.
  - **Shooting into the light** (key beyond 150°) gives a silhouette and a rim. It's dramatic, but it needs a fill or rim to keep the shape readable.

## 8. Continuity

- **The 180° line.** Between the two subjects that matter (Voyager and Earth), keep the camera on one side, through the scene and into the next. Then Earth stays on the same side of the screen. Cross the line only on screen, during a move, so the viewer sees it happen.
- **Screen direction.** Forward travel keeps one direction across scenes: for Voyager, outward from the Sun is left to right. Reversing it says "going back".
- **Matching across a transition.** A match cut aligns the shared object's position and size within about 5% of the frame.

## 9. The shot plan

Write one line per beat, before any key exists:

```
beat  time    subject     size          angle  side        lens  motive      note
1     0-3.5   voyager     medium wide   low    left third  35    establish   dish three-quarters on, lead room right
2     3.5-9   thrusters   close         eye    centre      50    emphasise   arrive by 8.3, the puff at 9
```

Then turn each line into a key with `shot()`, and check the key-pose dailies before rendering anything long.

## 10. Checklist (what review looks for)

- Every beat has a subject, a size and a motive, and the frames match the plan.
- No grazing edge cuts. Non-subject foreground covers under 25% of the frame, unless planned. Nothing else covers over 35% of the frame and more than twice the subject's share.
- Lead room on the side the subject faces or moves towards. Headroom 5–15% in medium and close shots.
- The camera arrives 0.5–1 s before each key action.
- At least two depth layers in most shots.
- Lens choices are deliberate and vary with the beat, not one focal length throughout.
- Speeds are inside the film profile, and the sheet raises no motion flags.
- The 180° line and screen direction hold.
