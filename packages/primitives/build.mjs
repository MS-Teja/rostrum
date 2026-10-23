// Bundles the primitives twice: an IIFE for compositions (window.Rostrum) and an ES module for Node scripts.
import { build } from "esbuild";
import { join } from "node:path";

const dir = import.meta.dirname;
const common = { entryPoints: [join(dir, "src/index.ts")], bundle: true, target: "es2022", logLevel: "warning" };

await build({ ...common, format: "iife", globalName: "Rostrum", outfile: join(dir, "dist/rostrum.js") });
await build({ ...common, format: "esm", platform: "node", outfile: join(dir, "dist/index.mjs") });
