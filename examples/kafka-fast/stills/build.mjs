// Collect the anchors Blender wrote next to each plate into plates/anchors.js,
// so the overlay can place labels without fetching anything at render time.
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const dir = join(import.meta.dirname, "plates");
const anchors = {};
for (const file of readdirSync(dir).filter((f) => f.endsWith(".anchors.json"))) {
  const { frames } = JSON.parse(readFileSync(join(dir, file), "utf8"));
  const [first] = Object.values(frames);
  anchors[file.replace(".anchors.json", "")] = first;
}
writeFileSync(join(dir, "anchors.js"), `window.ANCHORS = ${JSON.stringify(anchors)};\n`);
console.log(`anchors for ${Object.keys(anchors).length} plates -> plates/anchors.js`);
