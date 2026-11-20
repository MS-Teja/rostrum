"""SVG to PNG: headless Chrome (sharp text, the same engine as the viewer), ImageMagick if
Chrome isn't there."""

import glob
import os
import shutil
import subprocess
import tempfile


def chrome():
    for p in [os.environ.get("CINE_CHROME", ""),
              *sorted(glob.glob(os.path.expanduser("~/.cache/puppeteer/chrome/*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")), reverse=True),
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", shutil.which("chromium") or "", shutil.which("google-chrome") or ""]:
        if p and os.path.exists(p):
            return p
    return None


def png(svg_text, size, out):
    w, h = size
    exe = chrome()
    if exe:
        with tempfile.TemporaryDirectory() as d:
            page = os.path.join(d, "page.html")
            with open(page, "w", encoding="utf-8") as f:
                f.write(f'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;background:#111317">{svg_text}</body></html>')
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                            f"--window-size={int(w)},{int(h)}", f"--screenshot={os.path.abspath(out)}", "file://" + page],
                           capture_output=True, timeout=180)
        if os.path.exists(out):
            return out
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False, encoding="utf-8") as f:
        f.write(svg_text)
        tmp = f.name
    subprocess.run(["magick", tmp, out], check=True)
    os.unlink(tmp)
    return out
