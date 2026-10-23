// Bundles the director CLI for Node.
import { build } from "esbuild";
import { join } from "node:path";

const dir = import.meta.dirname;
await build({
  entryPoints: [join(dir, "src/cli.ts")],
  bundle: true,
  platform: "node",
  format: "esm",
  target: "node22",
  outfile: join(dir, "dist/cli.mjs"),
  logLevel: "warning",
});
