# Script: How Kafka partitions work

Voice: af_heart · Speed: 1.0 · Pause between beats: 0.3 s

Each beat has three lines: **Say** is spoken (`[cue]` marks the word an animation starts on), **Show** is the visual intent, and **Facts** points at `facts.md`.

## b1 · set up the problem
Say: Think of a Kafka [topic] as a log. Every event goes on the end, in order. But one log means one place to write. So what happens when a million events arrive [at once|rush]?
Show: one long log labelled with its topic; the producer pushes events onto its end, faster and faster, until they queue at the entrance.
Facts: F2, F8

## b2 · reveal: partitions
Say: Kafka splits a topic into [partitions]: separate logs, on different brokers, all written [at the same time|parallel].
Show: the log splits into three lanes, partitions 0, 1 and 2, each tagged with its broker; events flow into all three and the queue clears.
Facts: F3, F4

## b3 · which lane? the key
Say: So which partition does an event go to? The producer hashes its [key]. Every event for [customer 42|c42] lands in the [same partition|same].
Show: keys appear on the events; customer 42's events turn accent and all land in partition 1, one after another.
Facts: F1, F5

## b4 · the misconception
Say: And they stay [in order|order]: a partition is read exactly as it was written. But there's [no order across partitions|across]. Order lives inside one log, not the whole topic.
Show: push in on partition 1 to show 42's events in sequence with their offsets; pull back to events for other customers in other lanes, with no order between lanes.
Facts: F6, F7

## b5 · reading in parallel
Say: To read, a [consumer group] splits the partitions: each one goes to [exactly one|one] consumer. Three partitions, three consumers, reading [side by side|parallel].
Show: three consumers appear on the right; each partition connects to one of them; three read pointers move at once.
Facts: F9, F10

## b6 · recap
Say: So: one topic, [many logs|recap]. The key picks the log, and order lives inside it.
Show: the whole picture moving: keys routed to lanes, lanes filling, consumers reading.
Facts: —
