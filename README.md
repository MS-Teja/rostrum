# Rostrum

An open-source director for explainer videos.

You give it a topic, such as "how Kafka works under the hood", and it:
1. researches the facts
2. plans how to teach them
3. writes the narration
4. storyboards every beat
5. builds the animation with [HyperFrames](https://github.com/heygen-com/hyperframes)
6. checks its own frames before you see the result

Every stage writes a file you can read and edit, and re-running rebuilds only what changed.

## Why

Rendering video from code is a solved problem. What's still missing is direction: deciding what to show, when to show it, and how, so that a video actually teaches. Rostrum is that missing layer.

## Status

Early. There's nothing to install yet.

The first proof is a 4–6 minute "How Kafka works under the hood", made with Rostrum and published here with its full source.

## The name

A rostrum is the camera stand that classic animation was shot on. It's also the platform a lecturer speaks from.

## License

[Apache-2.0](LICENSE)
