# The director

The director owns the scene as a whole:
- why it exists
- what the viewer must come away with
- how it moves through time
- how it joins its neighbours

On a small production that includes the editor's job (pacing and transitions) and the script supervisor's (continuity). The director writes the **brief** first, and every other role works from it.

## 1. Think in scenes, not shots

A scene is one continuous action and one camera journey. The viewer should feel one movement, with intent at every beat, not a sequence of poses.
- **Inside a scene, the camera doesn't cut.** It travels between beats (cine's keyed rig), and the same object means one continuous move.
- **Between scenes there's a designed transition** (section 4), never a default cut.

## 2. The brief

Write it before anything is built, at the top of the scene file:

```
scene      reel-a-hero
purpose    what this scene does in the video, in one sentence
remember   the one thing the viewer must take away
journey    the camera's path in one sentence ("open on the dish, push in to the thrusters as they fire,
           rise over the rim, pull back as the beam reaches Earth")
feeling    how it should feel (quiet awe, tension, release)
beats      time range, the narration words it rides, what happens, the dominant motion
           (camera or actor), and the beat's subject
```

Each beat has exactly one subject and one dominant motion. If a beat needs two, split it.

## 3. Pacing

- **One idea per beat.** A narration sentence usually carries one idea, so give it one beat.
- **The voice sets the pace.** The voiceover's speed and energy (`core/voice.py`) scale how fast the camera may move, moment by moment. A fast, excited line can carry a brisk move; a slow, quiet line asks for a still or gentle camera. The sheet shows the pace curve under the words.
- **Moves ride the words.** A move starts on the word that motivates it, and lands before the word its action belongs to, within about 0.3 s. The words lane on the sheet shows this. The camera arrives 0.5–1 s before the action (see the cinematographer guide). Place keys by words (`voice.at("fire")`), not by seconds.
- **Still or slow under the voice.** While the voice explains what's already in frame, the camera holds still or creeps slowly one way. Move faster when the story moves: a new subject, a reveal, an emphasis.
- **Hold what matters.** Hold an important image for at least 2 s, so it can be read. Hold the scene's "remember" image longest.
- **Keep it fed.** Give something new every 3–6 s: a new subject, a reveal, a change of size, an actor's action, or a new idea in the voice over a held frame. Silence with nothing moving for over 4 s feels dead; the sheet flags it.
- **Breathe.** After a big move or a big reveal, give the viewer a slower beat to take it in before the next.

## 4. Transitions between scenes

Choose one per boundary and write it in both scenes' briefs:

| Transition | When | How |
|---|---|---|
| match cut | Two scenes share an object or a shape | Align the shared object's screen position and size within 5% of the frame across the cut |
| push-through | Going inside something | Fly into an object until it fills the frame, and come out in the next scene |
| zoom-through | A change of scale (craft to solar system to stars) | One continuous move across scales. Mark the key's motive `"zoom-through"`: the aim crosses scales in proportion to the view, and the zoom may run up to about one power of ten per 0.8 s, gliding from rest to rest. Hold at each scale long enough to read it (1.2 s or more) |
| whip pan | An energetic change of place | Fast pan with motion blur, matched in direction on both sides |
| light wipe | A change driven by light (the Sun, a signal) | A bright element crosses the frame and reveals the next scene |
| matched dissolve | Change of time at the same place | 0.5 s dissolve with the composition matched |

## 5. Continuity

- **Screen direction and the 180° line** hold across scenes (see the cinematographer guide).
- **Light direction** holds across scenes (see the look guide).
- **Object state** carries over. What was on stays on; what moved stays moved; damage, deployed parts and the time on clocks are kept.
- **Facts.** Every number, date and name on screen or in the narration cites a fact in the video's `facts.md`.

## 6. Teja's standing rules

- **3D always**, never a 2D or photo substitute. No AI-generated video.
- **Real data** for science scenes (Horizons, HYG, measured parts). Cheats are uniform and labelled.
- **On-screen text** is only numbers and dates, identifying names, and honesty notes. Never a phrase that repeats the voice.
- **Continuous camera:** the same object means one continuous move; a scene change means a designed transition.
- **The bar is Cleo Abram level.** "Slightly better than before" is not the bar.

## 7. The production loop

1. **Brief** (director).
2. **Shot plan** (cinematographer), then keys with `shot()`.
3. **Set and assets** (look), then **light** (look), then **actor motion** (animator).
4. **Dailies:** `python3 -m cine.dailies` renders the key poses, with automatic checks.
5. **Review:** the reviewer agent reads the dailies against the four guides. Answer every note in the scene's `notes.md`: fixed, or declined with the reason.
6. **Preview render**, then the motion sheet and frame checks.
7. **Teja.**

## 8. Checklist (what review looks for)

- The brief exists. Every beat has one subject, one dominant motion and its words.
- Moves start and land on their words, the camera arrives before the action, and the pace follows the voice. There's no wandering or fidgeting camera.
- Something new every 3–6 s, and the "remember" image holds longest.
- Transitions are designed, and continuity holds: direction, light, object state.
- The standing rules hold.
