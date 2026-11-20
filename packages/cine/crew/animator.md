# The animator

The animator moves everything in a scene that isn't the camera:
- machines and parts
- light that switches on
- signals travelling
- gas puffing
- paths drawing themselves

The aim is that motion feels physical and intentional, and that it plays with the camera, not against it. Every actor's motion is a curve in the motion file, drawn on the sheet like the camera's.

## 1. The principles, applied to objects

Classical animation's principles hold for machines as well as characters:

- **Timing.** How long something takes is what it weighs.
  - A puff blooms in 2–3 frames and fades over 0.3–0.6 s.
  - A large antenna or boom turns over seconds.
  - A light switches in 1–2 frames, and a warm filament over 0.2–0.4 s.
- **Ease, true to its cause.** Powered motion eases in and out (minimum-jerk). Things pushed by an impulse change speed at once, then coast. A thruster puff reverses a rotation sharply and the craft coasts. Don't ease what physics doesn't ease.
- **Anticipation.** Before a big action there's a small counter-move or a pause, so the eye knows something is coming. A mechanism might twitch back before it swings out, or a light flicker before it holds.
- **Follow-through and overlap.** Parts don't stop together. A boom stops, then its tip settles; flexible parts lag the body; a puff keeps drifting after the thruster closes.
- **Secondary motion.** Quiet life under the main action: a slow spin, a drift, a gentle idle. It must never compete with the main action (rule 2).
- **Arcs.** Natural paths curve. A straight line looks mechanical, which is right only for machines doing straight things.
- **Staging.** One action at a time, placed where the camera is looking.

## 2. One dominant motion

At any moment either the camera leads or an actor leads, never both at full strength.
- **When an actor's key action happens,** the camera has arrived and slowed: the cinematographer's "arrive 0.5–1 s before".
- **When the camera makes a big move,** actors are quiet or idling.
- **The check:** cine measures each actor's on-screen motion with the same kinematics as the camera. A peak in actor motion during a camera sweep or zoom above the reference band is flagged as competing motion.

## 3. Truth in motion

- **Real data.** Motion follows the real data where it exists: trajectories from Horizons, rotation rates, deployment sequences.
- **Time cheats.** Compressing time is usually necessary (an attitude cycle that really takes hours, shown every 3 s). Make it uniform, and declare it in the scene's notes and, if it matters, on screen.
- **Physics stays consistent.**
  - Thrusters fire in pairs that make the turn they're shown to make: a couple from opposite clusters, with the turn about the axis that couple produces.
  - Light travels at a stated speed; a beam reaching Earth takes the time the story says it does.

## 4. Presets

cine's actor presets (`cine.blender.actors`, being built) write their keys onto curves, so they show on the sheet:
- **appear and disappear:** scale or fade, with a small overshoot (5–10%), settling in 0.3–0.5 s
- **burst or puff:** a fast bloom, slower fade, drift
- **glow pulse:** rise, hold, decay
- **path draw:** a curve drawing itself along its length, minimum-jerk or at a steady speed
- **pulse along a path:** a signal travelling a curve at a set speed
- **ride:** an object following a data track (a trajectory)
- **idle:** slow spin or drift, for secondary motion

## 5. Checklist (what review looks for)

- Every actor's timing fits its size and its cause: powered moves ease, impulses snap.
- Big actions are anticipated, and there's follow-through after them.
- One dominant motion: no actor action competes with a camera move.
- The camera has arrived before each key actor action.
- Motion follows real data and consistent physics. Time cheats are uniform and declared.
