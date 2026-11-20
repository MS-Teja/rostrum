# The look: light, assets and grade

On a small production, three jobs are often one person, and here they are one role:
- **gaffer:** lights the scene
- **production designer:** builds and dresses it
- **colorist:** grades it

The look role makes the picture readable, true and beautiful, in that order. Exposure numbers are measured on the rendered stills (display values 0–1 after AgX, luminance by Rec. 709 weights) inside a subject mask. cine checks them automatically.

## 1. Light: motivated by a real source

Every light has a reason: a real source in the scene, or a declared cheat.

**Space.**
- **The key is the Sun.** A hard key (small angle, about 0.5°), from the Sun's true direction. From the outer solar system, the Sun and Earth sit within a fraction of a degree of each other, so a dish pointed at Earth is lit face-on.
- **The fill is a cheat.** Space has no fill, so the shadow side is truly black. Add a cool fill at most 1/30 of the key (about 5 stops down), so shapes stay readable, and declare it.
- **A subject that never sees the Sun gets a local light.** Some parts sit permanently in shadow; Voyager's bus is always behind its dish. When such a part is the beat's subject, add a declared local light near it, up to 1/8 of the key:
  - a small soft light on the camera's side, falling off before it reaches sunlit surfaces;
  - never casting a shadow that contradicts the Sun.

  The part then reads, and the sunlit parts are unchanged. Without it, a close-up of the part is a black frame until something lights it.
  - Near a planet, the planet's own reflected light is a real fill. Earthshine is bluish; a gas giant's light is warm.
- **The rim separates the subject from black.** Put it behind and above. Keep it at most half the key; a rim brighter than the key flattens the subject into a cut-out. Scene A's first rim did exactly that to the back of the dish.

**Interiors.** Light from the practical sources: screens, LEDs, ceiling panels, a window. Each is a real light near its prop. Add the ambient as an environment light, not a flat fill.

**Where the key sits** relative to the camera (the cinematographer's choice, the look role's concern):
- **Side or three-quarter key** (45–120° from the lens axis) shows form. Prefer it.
- **Front key** (within 20° of the axis) flattens.
- **Backlight** (beyond 150°) is a silhouette. It's dramatic, and it needs a rim or fill to keep the shape.

**Light direction stays put.** Across scenes the light direction stays consistent in the world, unless the story moves the light.

## 2. Exposure and separation (checked)

All values are measured inside the subject mask unless stated.

| Measure | Target |
|---|---|
| Subject median luminance | 0.20–0.60. Below that the subject is murky; above it, washed out. |
| Subject against background | Median contrast ratio at least 3:1 (subject over background, with a 0.02 floor on the background). Against a black sky, aim for 5:1 or more. |
| Clipped (luminance ≥ 0.98) on the subject | Under 2%. Emissive and specular highlights are allowed, and live in their own mask. |
| Crushed (luminance ≤ 0.02) on the subject | Under 35%. In space a large shadow side is true, but the whole subject going black is not readable. |
| Flatness: the spread (90th minus 10th percentile) of subject luminance | At least 0.15. A subject that's one flat grey has lost its form, as the dish back did. |

**A planned look changes the targets.** A shot plan can declare its look, and the checks judge the still by it (`cine/core/look.py`):
- **low-key:** a dark subject by nature or by design, such as black thermal blankets, or a part that never sees the Sun. It's judged on separation and form, not brightness: median from 0.03, contrast at least 2.5:1, crushed under 50%, spread at least 0.15.
- **silhouette:** a subject against the light. Its rim must read: the 90th percentile at least 0.30, and 5:1 against the background.

Say why in the shot plan. A planned look is a decision, not an excuse.

## 3. Assets: real first

- **Models.** Use the real ones (NASA's 3D models are public domain). Measure features off the model, never guess them, and record each measurement in a code comment.
- **Textures:**
  - **Earth:** NASA's Blue Marble (public domain).
  - **Planets and moons:** NASA and USGS maps.
  - **Stars:** the HYG catalogue's real positions. Brightness comes from magnitude (each magnitude is ×0.4 in flux; draw size and strength from that), and colour from the B−V index.
- **Materials.** Use real-world albedo:
  - white paint 0.7–0.8, never 1.0
  - bare aluminium: metallic, roughness 0.3–0.5
  - gold or amber kapton foil: metallic and wrinkled
  - black paint 0.04–0.08

  Pure white with uniform light reads as a flat cut-out. Add roughness variation, or ambient occlusion, to large panels.
- **Scale cheats.** A cheat is uniform (one factor for everything of its kind) and declared in the scene's notes and provenance list, as "Earth: 1.6 m at 46 m, a prop". If a cheat would make the viewer believe something false, label it on screen with an honesty note.
- **Provenance.** Each scene lists its assets with source and licence, so credits and honesty notes are exact.
- **Effects:**
  - **Gas** (thruster puffs, exhaust): soft, see-through and short-lived. It's brightest at the nozzle and fades along its length (`look.plume`). A real hydrazine puff in vacuum is nearly invisible, so declare it as drawn.
  - **Beams and signals:** a thin core with a soft glow. The width stays constant on screen at any distance (a scale-aware driver), so the beam reads as a line, not a rod.

## 4. Grade: the look changes per story

- **The base.** Use AgX ("Medium High Contrast" by default). Exposure is set once per scene, from the subject's median, not per frame.
- **The story's look.** Each video picks one in its style notes. For example:
  - Voyager: cold and deep: blue-black shadows, warm only in the signal and the Sun.
  - A server room: cool neutral with saturated status LEDs.
- **Consistency.** Adjacent scenes stay within 0.05 of each other in median luminance and saturation, unless the story is changing mood.
- **Bloom.** Use it only on emissive and specular light, with a threshold of at least 1.0 (`look.glow`). Bloom on everything is haze.
- **Motion blur.** Always on, with a 180° shutter (0.5 frame). It's what makes motion read as filmed.

## 5. Checklist (what review looks for)

- Every light has a source or a declared cheat.
- The fill is 1/30 of the key or less (a local light on a permanently shadowed subject, up to 1/8), and the rim is half the key or less.
- The subject's exposure, contrast, clipping, crush and spread are all in range.
- The assets are real. Cheats are uniform, declared and listed with their source.
- No plastic white: large panels show their form.
- Bloom sits only on what glows, and motion blur is on.
- The grade matches the story's look and the neighbouring scenes.
