"""The scene viewer: one HTML page with the motion sheet, the director's map and the picture
(a preview video or a filmstrip), all driven by one scrubber. Drag it and a cursor moves along
every curve, the camera glyph moves along its path on the map, and the video seeks to the same
frame. Read-only; self-contained (open the file, no server)."""

import html
import json
import os

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#0d0f12;--card:#15181d;--ink:#e9e7e2;--mute:#8b8f98;--line:#262a31;--accent:#ffb13b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 Inter,-apple-system,system-ui,sans-serif}
header{position:sticky;top:0;z-index:5;background:rgba(13,15,18,.96);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
h1{font-size:17px;margin:0;font-weight:650}#t{font-variant-numeric:tabular-nums;color:var(--accent);min-width:150px}
input[type=range]{flex:1;min-width:240px;accent-color:var(--accent)}button{background:#232831;color:var(--ink);border:1px solid #333a45;border-radius:6px;padding:5px 12px;font:inherit;cursor:pointer}
main{padding:12px 16px 60px;display:grid;gap:14px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;overflow-x:auto}
.card h2{font-size:13px;margin:0 0 8px;color:var(--mute);font-weight:600;text-transform:uppercase;letter-spacing:.06em}
.wrap{position:relative;display:inline-block}.wrap svg{display:block;max-width:none}
#flags{font-size:13px;columns:2;column-gap:28px}#flags div{break-inside:avoid;padding:2px 0;cursor:pointer}#flags b{color:#ff5a5a}
video{max-width:min(960px,100%);display:block;border-radius:6px}
</style></head><body>
<header><h1>__TITLE__</h1><button id="play">Play</button><input id="scrub" type="range" min="0" max="1000" value="0"><span id="t"></span></header>
<main>
__VIDEO__
<section class="card"><h2>Motion sheet: every curve, start to finish</h2><div class="wrap" id="sheetwrap">__SHEET__</div></section>
<section class="card"><h2>Director's map</h2><div class="wrap" id="mapwrap">__MAP__</div></section>
<section class="card"><h2>Flags</h2><div id="flags">__FLAGS__</div></section>
</main>
<script>
const D = __DATA__;
const scrub = document.getElementById('scrub'), tl = document.getElementById('t'), vid = document.getElementById('vid');
const ns = 'http://www.w3.org/2000/svg';
const sheet = document.querySelector('#sheetwrap svg'), map = document.querySelector('#mapwrap svg');
const cursor = document.createElementNS(ns, 'line');
cursor.setAttribute('stroke', '#fff'); cursor.setAttribute('stroke-width', '1.5'); cursor.setAttribute('opacity', '0.85');
cursor.setAttribute('y1', 0); cursor.setAttribute('y2', D.sheetH); sheet.appendChild(cursor);
const glyphs = D.views.map(v => { const c = document.createElementNS(ns, 'circle'); c.setAttribute('r', 7); c.setAttribute('fill', 'none');
  c.setAttribute('stroke', '#fff'); c.setAttribute('stroke-width', 2.5); map.appendChild(c); return c; });
function show(t, fromVideo) {
  t = Math.min(D.t1, Math.max(D.t0, t));
  const x = D.x0 + (t - D.t0) / (D.t1 - D.t0) * (D.x1 - D.x0);
  cursor.setAttribute('x1', x); cursor.setAttribute('x2', x);
  const f = Math.round((t - D.t0) * D.fps);
  D.views.forEach((v, i) => { const p = v.pts[Math.min(f, v.pts.length - 1)]; glyphs[i].setAttribute('cx', p[0]); glyphs[i].setAttribute('cy', p[1]); });
  tl.textContent = t.toFixed(2) + 's  (frame ' + f + ')';
  scrub.value = Math.round((t - D.t0) / (D.t1 - D.t0) * 1000);
  if (vid && !fromVideo && Math.abs(vid.currentTime - (t - D.t0 + D.videoOffset)) > 0.04) vid.currentTime = t - D.t0 + D.videoOffset;
}
scrub.addEventListener('input', () => show(D.t0 + scrub.value / 1000 * (D.t1 - D.t0)));
document.querySelectorAll('#flags div').forEach(el => el.addEventListener('click', () => show(+el.dataset.t)));
let playing = null;
document.getElementById('play').addEventListener('click', e => {
  if (vid) { vid.paused ? vid.play() : vid.pause(); return; }
  if (playing) { clearInterval(playing); playing = null; e.target.textContent = 'Play'; return; }
  e.target.textContent = 'Pause'; let t = D.t0 + scrub.value / 1000 * (D.t1 - D.t0);
  playing = setInterval(() => { t += 1 / D.fps; if (t > D.t1) t = D.t0; show(t); }, 1000 / D.fps);
});
if (vid) vid.addEventListener('timeupdate', () => show(D.t0 + vid.currentTime - D.videoOffset, true));
show(D.t0);
</script></body></html>"""


def write(path, title, sheet_svg, sheet_h, sheet_obj, map_svg, map_data, flags, motion, video=None, video_offset=0.0):
    fl = "".join(f'<div data-t="{t0:.3f}"><b>{html.escape(kind)}</b> {t0:.2f}s · {html.escape(msg)}</div>' for kind, t0, msg, _t1 in flags) or "<div>none</div>"
    vid = ""
    if video:
        rel = os.path.relpath(video, os.path.dirname(os.path.abspath(path)))
        vid = f'<section class="card"><h2>Picture</h2><video id="vid" src="{html.escape(rel)}" controls preload="auto"></video></section>'
    data = {"t0": motion.t0, "t1": motion.t1, "fps": motion.fps, "x0": sheet_obj.x0, "x1": sheet_obj.x1, "sheetH": sheet_h + 8,
            "views": map_data["views"], "videoOffset": video_offset}
    page = (PAGE.replace("__TITLE__", html.escape(title)).replace("__VIDEO__", vid).replace("__SHEET__", sheet_svg)
            .replace("__MAP__", map_svg).replace("__FLAGS__", fl).replace("__DATA__", json.dumps(data)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path
