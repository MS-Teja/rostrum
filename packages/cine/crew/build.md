# How to build a scene

The four role guides ([director](director.md), [cinematographer](cinematographer.md), [look](look.md), [animator](animator.md)) hold the rules. This guide holds the **order** you apply them in, and the **evidence** each step leaves behind.

**Why it exists.** The reviewer wrote 43 notes on the cine reel's scenes A, B and C, ten of them "must". Almost every one could have been caught before any 3D existed, and most broke a rule the guides already had. Scene C had no "remember" image although the director's guide asks for one, because the scene was written straight into code. The rules were there; the order wasn't.

**The five families of mistakes** the reviews found, and the gate that now catches each:

| Family | Seen in the reel | Caught at |
|---|---|---|
| 1. The subject doesn't read at its word | A's dark backlit end, A's murky close-up, B's faint pulse, C's pulse hidden under a tray and its anonymous server | 1, 4, 6 |
| 2. Timing against the words | A's puff fired at the zoom peak, B's zoom landed late, A's beam grew during the fastest move | 1, 5, 6 |
| 3. A weak or static ending | A's tiny Earth at the frame edge, B's 13.7 s creep, C's 8.7 s of stillness | 1, 5 |
| 4. Crude stand-in assets | C's slab chip and static-like "crunch", A's cut-out puff, A's uniform stars | 2, 3 |
| 5. The plan not delivered | A's rise over the rim that never happens, A's lens that never changes | 5 |

**How the gates work.**
- Work through them in order.
- Each gate **produces** something saved with the scene, **answers** its questions in writing in the scene's `notes.md` (under "Build"), and runs its **checks**.
- A gate isn't passed until its evidence exists. The reviewer checks that it does.
- **Teja approves three gates:** the paper plan, the look, and the final render.
- Start a scene from the templates: `templates/scene.py` and `templates/notes.md`.

| Gate | Produce | Check | Teja |
|---|---|---|---|
| 1. Paper | The brief: last image, seen at word, handles | Read against the take | approves |
| 2. References | Real references; the features that make each hero object read | Real-data rule | |
| 3. Hero proof | The hero object alone, lit, at its closest shot | Look checks | approves 3 + 4 together: the look |
| 4. Set and light | The set; a still at each key | Look checks | (with 3) |
| 5. Blocking | Camera keys by words | `cine.see`: 0 motion and composition flags | |
| 6. Actors | Actor motion, each with a track | Actor visibility | |
| 7. Dailies | The pack; the checklist answered | Every check; then the reviewer, once | |
| 8. Render | The render, the join, the notes log | The join's voice check; a frame scan | approves |

Problems found at gates 1–4 cost minutes. Found at review, they cost a round of dailies. Found by Teja at the end, they cost a re-render and Teja's trust.

## Gate 1. Paper (Teja approves)

Before any code beyond the take's timing, write the brief at the top of the scene file. It has the director's fields (purpose, remember, journey, feeling, beats, in, out, light, cheats) and three more that are required:

- **last image**: the "remember" as a picture. Say what's in frame, the subject's shot size, what (if anything) moves, and how long it's held. Hold it at least 2 s, and longer than any other image. An ending is a held picture, not a long creep.
- **seen at word**: a table, one row per beat:

  ```
  word        what must be visible            size      lit by
  "flash"     the pulse, on the tray's fibre  small     its own glow, against the dark ceiling
  "building"  the server it drops into        wide      its amber strip lighting
  ```

  Every word that names something has a row. If a row can't be filled, the beat isn't designed yet.
- **handles**: in and out, each at least the transition on that side plus 0.25 s (director §4). The voice is never under a transition. Be generous: a transition can take its own time (1–2 s), and the next scene's action needn't start the instant it opens. Hold the last image after the voice.

Answer in `notes.md`:
- Read the beats against the take. Is every subject on screen, readable, by its word?
- Does each beat have one subject and one dominant motion?
- Does the camera arrive 0.5–1 s before each action, not during it?
- Is there something new every 3–6 s?
- Is the ending a held picture, the longest hold?

**Teja approves** the brief and the seen-at-word table. Send them short: the last image first.

## Gate 2. References

For each **hero object** (anything shown at medium or closer), produce:
- **Real references**: photos, NASA models, papers, measured parts, data files. List them in the brief's `references`. Images stay private in `research/refs/` (gitignored).
- **Its 3–5 readable features** at its closest planned shot: what a viewer who knows the object checks first. For a GPU: the die's tile grid, memory stacks either side of it, a substrate edged with capacitors, and traces that end on pads.

The closest shot sets the detail. In close-up, model every listed feature; in a wide, the silhouette and its lights are enough.

Answer in `notes.md`: what does the real thing look like at that size, and which feature would give a fake away?

## Gate 3. Hero proof (Teja approves, with gate 4)

Render the hero object **alone** (the set hidden, its planned key light on) at its closest planned shot, and at its widest: 1–3 stills, seconds each (`--proof` in the template).

Answer in `notes.md`:
- Does every listed feature read?
- Does anything look like a stand-in: a flat slab, uniform dots, a cut-out cone, a primitive where a part should be?
- Activity (data, computation, gas, flow) needs structure: a direction, a source, waves, a cause. Random noise reads as TV static.

Check: the look checks on the stills. "Flat" means the form doesn't read: change the light, not the threshold.

## Gate 4. Set and light (Teja approves the look: gates 3 and 4)

Build the set around the hero, light it, and render a still at each camera key, before any animation (`--dailies` with the actors not yet built).

Answer in `notes.md`:
- Is every light motivated and declared in the brief (look §1)?
- Does the subject separate from what's behind it?
- **Is the brightest thing in each frame the thing that matters?** In scene C's first cut, the floor, the end of the aisle and a shiny cable tray outshone the server the story was about.
- What do the shiny surfaces reflect? Is anything near a light burned out?

Check: the look checks pass on every key still.

**Teja approves the look:** the hero proof stills and the key stills, together.

## Gate 5. Blocking

Place the camera keys by words: `voice.at("word")` with `Framer.shot()`, `hold()` or `Rig.place()`. Never by raw seconds.

Answer in `notes.md`:
- Does each move start on its word and land on the word its action belongs to, within 0.3 s?
- Is the camera still or slow under explaining lines?
- Is the last image held as the brief says?
- Does the lens change with the beat, and does every planned move actually happen (an elevation that should climb, climbs)? Read the measured values on the sheet, not the keys.
- Does the camera stay inside every opening it passes through? Compute it.

Check: `python3 -m cine.see scene.motion.json --profile profiles/explainer.json` gives 0 motion and composition flags.

## Gate 6. Actors

Build the actor motion with the presets (`cine/blender/actors.py`). Give each actor a **track** in the motion file, so the checks can see it.

Answer in `notes.md`, for each actor at its word:
- **In frame?**
- **Not hidden?** Think from where the camera is. Scene C's pulse ran on top of a cable tray; from the aisle you only ever see the tray's underside.
- **Big enough?** At least 0.006 of the frame's width.
- **Standing out from what's behind it?** A white pulse on a bright, shiny tray vanishes.
- **Not competing with the camera?** An actor's action doesn't land on the camera's fastest moment (animator §2).

Check: the actor visibility check (`cine.see` for frame and size; the dailies for hidden). On-screen text is checked here too: the text check (`core/text.py`) flags labels that are brief, moving, re-placed, ticking, flashing or crowded.

## Gate 7. Dailies and self-review

Run the dailies (`--dailies`) and answer **the checklist** below in `notes.md`: for each item, yes, or what you changed. Look at every still yourself. The checks catch numbers, not meaning: scene C's first cut had zero flags and a pulse no one could see.

Then run the reviewer agent once (`cine-reviewer`). Answer every note in `notes.md`: fixed, or declined with the reason. A second run happens only if the first raised "must" notes.

## Gate 8. Render (Teja approves)

Render the preview (`--render`), join it into the film or reel (`transition.join` refuses voice under a transition), and scan the frames: `python3 -m cine.frameqa scene.mp4` flags pops and flicker (skip designed fades with `--skip`). It reads the picture itself, so it catches what the camera checks can't: scene b07's first render had the Sun whip across the frame as the camera passed it, and only this scan saw it. Complete `notes.md`.

**Teja approves** the render, with the notes log beside it.

## The checklist

One list, used by whoever builds the scene at gate 7 and by the reviewer:

1. **Seen at word.** Every row of the brief's table is true in the stills: the thing is visible, readable and lit at its word.
2. **Timing.** Moves start and land on their words; the camera arrives before the action; one dominant motion at a time.
3. **The last image.** It's the picture the brief promised, held longest, and it says the "remember" line.
4. **No stand-ins.** Every hero object shows its listed features at its closest shot; activity has structure.
5. **The plan delivered.** Every planned move, lens change and reveal happens on the sheet.
6. **The brightest thing matters.** Nothing outshines the subject; nothing burns out.
7. **The voice is clear.** Handles are at least the transitions; no word falls under a transition.
8. **Text stays put.** Each label takes one place when it appears and holds it until it leaves: never re-placed during a shot, never fading with the camera's motion. Show a name while its subject holds still on screen; put dates and readouts in one corner for the whole scene, as held values shown while they're true (no counters ticking every frame). Text changes are few, and each is held long enough to read. Teja's note on a scene where labels dodged lines and readouts ticked: "it's too messy. Texts are constantly changing, they should be at a constant place." Check: the text check (`stage.text_flags()`, passed to the dailies pack as `text=`) gives 0 flags.
9. **Each role's own checklist:** director §8, cinematographer §10, look §5, animator §5.
