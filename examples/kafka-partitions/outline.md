# Teaching plan: How Kafka partitions work (60 s)

**Who it's for:** developers who know what a message queue is but haven't looked inside Kafka.

**The question, asked in the first 10 seconds:** if every event goes on the end of one log, what happens when a million arrive at once? "A million" is a hypothetical, not a claim about Kafka.

**The mental model to leave behind:** a topic isn't one log. It's several logs side by side (partitions). The key decides which log an event goes in, and order only exists inside one log.

**Parts, each shown and named before it's used:**
- event (with its key)
- topic
- partition
- offset
- consumer group

## Beats

| # | Purpose | What the viewer sees | What they should feel or know | Facts |
|---|---|---|---|---|
| 1 | **Set up the problem** | One long log. A producer pushes events onto its end, faster and faster, and they start queuing at the entrance. | "One line, one place to write. This can't keep up." | F2, F8 |
| 2 | **Reveal: partitions** | The single log splits into three lanes, labelled partition 0, 1 and 2, each on its own broker. Events now flow into all three at once and the queue clears. | Relief: the bottleneck was having only one log. | F3, F4 |
| 3 | **Which lane? The key** | Every event shows its key, a customer ID. Customer 42's events are the accent colour, and all of them land in partition 1, one after another. | Same key, same lane, always. | F1, F5 |
| 4 | **The misconception** | Zoom into partition 1: 42's events are in perfect order. Pull back: events for other customers sit in other lanes, with no order between lanes. | "Order is per partition, not per topic." Spoken outright. | F6, F7 |
| 5 | **Reading in parallel** | A consumer group of three. Each consumer locks onto one partition, and three read pointers move at once. | More partitions means more consumers reading side by side. | F9, F10 |
| 6 | **Recap** | The whole picture moving: keys routed to lanes, lanes filling, consumers reading. | The model in one sentence. | — |

## Reveals and their setups

- **Partitions (beat 2)** are set up by the queue in beat 1. The viewer should feel the bottleneck before the split happens.
- **Per-partition order (beat 4)** is set up by beat 3. Watching 42's events land in order makes it natural to assume the whole topic is ordered. Beat 4 shows otherwise.

## Visual vocabulary (fixed for the whole series)

- **Event:** a rounded square with its key on it. Neutral by default. The accent colour marks only the key the narration is about (customer 42).
- **Partition:** a horizontal lane of events with offsets underneath. A partition always keeps the same position and label.
- **Producer:** a pill on the left. **Consumers:** pills on the right.
- **Camera:** a wide shot for the setup, a push-in on partition 1 for the ordering beat, then a pull-back for consumers and the recap.
