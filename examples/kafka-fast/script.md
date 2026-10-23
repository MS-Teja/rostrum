# Script: Why Kafka is fast (15 s animation test)

Voice: af_heart · Speed: 1.0 · Pause between beats: 0.3 s

Each beat has three lines: **Say** is spoken (`[cue]` marks the word an animation starts on), **Show** is the visual intent, and **Facts** points at `facts.md`.

## b1 · the usual path
Say: Normally, sending stored data takes [four copies|four]: disk to [page cache|cache], up into [Kafka's memory|user], back down to a [socket buffer|socket], then out to the [network card|nic].
Show: the glass-ceiling set; a lit tile travels the path and leaves a copy at each stop as it's named, numbered 1 to 4; rings flash as it crosses the glass.
Facts: F1

## b2 · sendfile
Say: With [sendfile], the data [skips the trip|skip]: page cache, [straight to the network card|straight].
Show: the user-space path and its copies dim; Kafka goes dark; one bright path runs from the page cache straight to the network card.
Facts: F2
