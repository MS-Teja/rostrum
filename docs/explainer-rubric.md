# Explainer rubric (v0)

This is what Rostrum's review step scores a video against, and the checklist a human reviewer uses. Rules marked **[auto]** are checked by code; the rest are judged by the critique model and by people.

Where a rule comes from research, the effect size (d) is from Richard Mayer's multimedia-learning experiments. Larger means a bigger improvement in what viewers learn: about 0.4 is moderate and 0.8 or more is large. Other numbers are starting values that we'll tune against reference videos.

## 1. Teaching (outline and script)

1. **One question drives the video.** State it within the first 10 seconds, in concrete terms. Example: "When you send a message to Kafka, where does it actually go?"
2. **Concrete before abstract.** Show one specific record moving before naming the general idea.
3. **Name the parts before the process** (pre-training, d ≈ 0.46). Introduce the producer, topic, partition, broker and consumer, each with its look, before showing how they work together.
4. **One idea per beat.** A beat is 1–3 sentences, usually 4–12 seconds.
5. **Reveal, don't label.** Before each "aha", show a problem the viewer can feel (for example, one log can't keep up), then show the mechanism that solves it (partitions). Every reveal in `outline.md` needs a setup beat before it.
6. **Clear up the main misconception out loud.** For example: "Order is guaranteed within a partition, not across a topic."
7. **End with the whole picture moving.** Recap in 15 seconds or less, with every part you introduced working together.
8. **Every factual sentence is sourced.** Each one in `script.md` points to an entry in `facts.md`. **[auto]** checks the links exist; the facts themselves need a human reviewer.

## 2. Narration

1. **Talk to the viewer** ("you", plain words, short sentences). This is the personalization principle.
2. **Pace:** start at 150–170 words per minute, with a short pause between beats. **[auto]** measures this from the word timestamps. We'll tune the target against reference videos.
3. **Don't put the narration on screen** (redundancy, d ≈ 0.86). On-screen text is labels and key terms, at most 5 words per element (titles excepted). **[auto]**
4. **Voice:** early studies found a human voice teaches better than a synthetic one, but those used robotic voices. Test our TTS voice against a human recording before we commit to either.

## 3. Picture and sync

1. **Show it when you say it** (temporal contiguity, d ≈ 1.30, the largest effect on this list). A visual event starts with its cue word, never more than 0.5 s before or after. Rostrum's cue sync targets ≤ 2 frames of drift. **[auto]**
2. **Labels sit on or next to what they name** (spatial contiguity, d ≈ 0.79). No legends.
3. **One focal point at a time** (signaling, d ≈ 0.41–0.46). The current focus gets the single accent colour, and everything else dims.
4. **Nothing decorative** (coherence, d ≈ 0.70–0.86). No motion, texture or element that doesn't serve the current idea. Music is optional, sparse and well below the voice, because background music can hurt learning.
5. **Consistent visual vocabulary.** The same thing always looks the same: partition 0 keeps its colour, shape and place for the whole video.
6. **Motion means something.** Movement shows data flow or change of state. The camera moves only to direct attention.
7. **Hold time:** a new state stays on screen until it can be read. That's at least 1 s plus 0.3 s per on-screen word, counted after its entrance animation ends. **[auto]**
8. **Legibility:**
   - Text is at least 32 px at 1080p, because many viewers watch on phones.
   - Text contrast is at least 4.5:1. **[auto]**
   - Nothing overlaps, clips or leaves the 90% safe area. **[auto]**
9. **Short chapters** (segmenting, d ≈ 0.70). Break the video into named chapters of 1–2 minutes, each ending on a stable picture.

## 4. Craft (the Apple-level look)

1. **Restrained palette:** two neutrals, one accent, one warning colour. Lots of empty space.
2. **Typography:** one family, 2–3 weights, one consistent size scale.
3. **Easing:**
   - No linear motion, except steady flows such as data streams.
   - Entrances ease out; moves ease in and out.
   - Object moves take 0.3–0.8 s, camera moves 0.8–1.5 s.
4. **Clean motion:** no popping, jitter or aliasing. Fast moves get motion blur.
5. **Transitions:** cut, or move the camera continuously between related beats. No spins, glitches or flashes unless they mean something.

## 5. Scoring

- The critique step scores sections 1–4 out of 5 each and lists concrete fixes as edits to the stage files.
- Any factual error blocks release, whatever the other scores.
- **[auto]** checks run on every render. A failing check is fixed before a human sees the video.
- Release decisions use human ratings, not the model's own scores.

## Sources
- Mayer, *Cambridge Handbook of Multimedia Learning*: [coherence, signaling, redundancy, spatial and temporal contiguity](https://resolve-he.cambridge.org/core/books/cambridge-handbook-of-multimedia-learning/principles-for-reducing-extraneous-processing-in-multimedia-learning-coherence-signaling-redundancy-spatial-contiguity-and-temporal-contiguity-principles/CD5B7AE1279A9AB81F8EEBB53DBEC86E)
- Summaries of all 12 principles: [Dartmouth](https://services.dartmouth.edu/TDClient/1806/Portal/KB/PrintArticle?ID=171655) · [Lucidea](https://lucidea.com/blog/mayers-12-principles-of-multimedia-learning)
