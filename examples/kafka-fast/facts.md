# Facts: Why Kafka is fast (zero-copy segment)

Every factual sentence in `script.md` points at one of these. Quotes are from the Apache Kafka design docs, [Efficiency][design].

| ID | Fact | Source |
|---|---|---|
| F1 | Sending file data to a socket the usual way takes four copies: disk to page cache, page cache to the application's user-space buffer, back into a kernel socket buffer, then to the network card's buffer. | "The operating system reads data from the disk into pagecache in kernel space"; "The application reads the data from kernel space into a user-space buffer"; "The application writes the data back into kernel space into a socket buffer"; "The operating system copies the data from the socket buffer to the NIC buffer". "There are four copies and two system calls." [Design][design] |
| F2 | With sendfile, the OS sends data from the page cache straight to the network; only the final copy, to the network card's buffer, is needed. | "Using sendfile, this re-copying is avoided by allowing the OS to send the data from pagecache to the network directly. So in this optimized path, only the final copy to the NIC buffer is needed." [Design][design] |
| F3 | Kafka writes data to its log on the filesystem, which in effect puts it in the kernel's page cache. | "All data is immediately written to a persistent log on the filesystem without necessarily flushing to disk. In effect this just means that it is transferred into the kernel's pagecache." [Design][design] |
| F4 | sendfile isn't used when SSL/TLS is enabled. | "Due to this restriction, `sendfile` is not used when SSL is enabled." [Design][design] |

**Simplification to watch:** "with sendfile, the data skips the trip" means it skips Kafka's user-space memory. It holds only without TLS (F4), which this 15 s segment doesn't claim either way; the full video must say it.

[design]: https://kafka.apache.org/43/design/design/
