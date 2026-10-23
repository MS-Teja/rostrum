# Facts: How Kafka partitions work

Every factual sentence in `script.md` points at one of these. Quotes are from the Apache Kafka docs.

| ID | Fact | Source |
|---|---|---|
| F1 | An event has a key, a value, a timestamp and optional headers. | "Conceptually, an event has a key, value, timestamp, and optional metadata headers." [Intro][intro] |
| F2 | Events are stored in topics. | "Events are organized and durably stored in topics." [Intro][intro] |
| F3 | A topic is split into partitions spread over different brokers. | "Topics are partitioned, meaning a topic is spread over a number of 'buckets' located on different Kafka brokers." [Intro][intro] |
| F4 | Partitions let clients read and write through many brokers at once, which is how Kafka scales. | Partition placement lets clients "read and write the data from/to many brokers at the same time", which the docs call "very important for scalability". [Intro][intro] |
| F5 | Events with the same key go to the same partition. The producer hashes the key to pick it. | "Events with the same event key (e.g., a customer or vehicle ID) are written to the same partition." [Intro][intro] Semantic partitioning: "specify a key to partition by and using this to hash to a partition". [Design][design] |
| F6 | A partition is read in exactly the order it was written. | A consumer reads a partition's events "in exactly the same order as they were written." [Intro][intro] |
| F7 | There's no total order across the partitions of a topic. | "Kafka only provides a total order over messages within a partition, not between different partitions in a topic." [0.9 docs][intro09] The current docs keep only the per-partition guarantee (F6). |
| F8 | A partition is an append-only log, and each event's offset is permanent. | "It has dense, sequential offsets and retains all messages." "The offset for a message never changes." [Design][design] |
| F9 | Within a consumer group, each partition is read by exactly one consumer at a time. | Each partition is "consumed by exactly one consumer within each subscribing consumer group at any given time." [Design][design] |
| F10 | A consumer's progress in a partition is one number: the offset of the next event to read. | "The position of a consumer in each partition is just a single integer." [Design][design] |
| F11 | Reading an event doesn't delete it. | "Events are not deleted after consumption." [Intro][intro] |

**Out of scope for this segment:** replication, leaders and followers, rebalancing, retention settings, delivery semantics. Each gets its own segment.

**Simplification to watch:** "the key picks the partition" holds while the partition count stays the same. Adding partitions changes where new events with a key land. It isn't said in this segment, so it isn't claimed.

[intro]: https://kafka.apache.org/43/getting-started/introduction
[design]: https://kafka.apache.org/43/design/design/
[intro09]: https://kafka.apache.org/090/getting-started/introduction/
