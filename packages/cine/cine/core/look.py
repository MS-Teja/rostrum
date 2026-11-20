"""The look role's exposure checks (crew/look.md), as rules on the measures of a still. Pure
Python, so the dailies can apply each shot's planned look.

A shot plan may declare its look (camera.shot: look=...):
  "normal"    a mid-tone subject: median 0.20-0.60, contrast at least 3:1, crushed under 35%
  "low-key"   a dark subject by nature or by design (black thermal blankets, a part that never
              sees the Sun): judged on separation and form, not brightness. Median from 0.03,
              contrast at least 2.5:1, crushed under 50%
  "silhouette" a subject against the light: its rim must read (90th percentile at least 0.30,
              5:1 against the background); median and crush aren't judged
"""

RULES = {
    "normal": {"median": (0.20, 0.60), "contrast": 3.0, "clipped": 0.02, "crushed": 0.35, "spread": 0.15},
    "low-key": {"median": (0.03, 0.60), "contrast": 2.5, "clipped": 0.02, "crushed": 0.50, "spread": 0.15},
    "silhouette": {"median": (0.0, 1.0), "contrast": None, "clipped": 0.05, "crushed": 1.01, "spread": 0.10, "rim": 0.30, "rim_contrast": 5.0},
}


def flags(m, look="normal"):
    """[(kind, message)] for one still's look measures under the planned look."""
    r = RULES.get(look or "normal", RULES["normal"])
    out = []
    if not m.get("subject_visible"):
        return out
    lo, hi = r["median"]
    if m["median"] < lo:
        out.append(("murky", f"subject median {m['median']:.2f} (under {lo}, {look or 'normal'} look)"))
    if m["median"] > hi:
        out.append(("washed", f"subject median {m['median']:.2f} (over {hi})"))
    if r.get("contrast") and m["contrast"] < r["contrast"]:
        out.append(("contrast", f"subject against background {m['contrast']:.1f}:1 (under {r['contrast']:g}:1)"))
    if m["clipped"] > r["clipped"]:
        out.append(("clipped", f"{m['clipped']:.0%} of the subject clipped"))
    if m["crushed"] > r["crushed"]:
        out.append(("crushed", f"{m['crushed']:.0%} of the subject crushed to black"))
    if m["spread"] < r["spread"]:
        out.append(("flat", f"subject spread {m['spread']:.2f} (under {r['spread']}): its form doesn't read"))
    if "rim" in r:
        if m["p90"] < r["rim"]:
            out.append(("rim", f"the rim doesn't read (90th percentile {m['p90']:.2f}, under {r['rim']})"))
        elif m["p90"] / max(m["background"], 0.02) < r["rim_contrast"]:
            out.append(("rim", f"the rim against the background is {m['p90'] / max(m['background'], 0.02):.1f}:1 (under {r['rim_contrast']:g}:1)"))
    return out


def planned(shots, subject, t):
    """The planned look for a still: from the shot-plan entry for this subject nearest in time."""
    best = None
    for s in shots or []:
        if s.get("subject") == subject and (best is None or abs(s["t"] - t) < abs(best["t"] - t)):
            best = s
    return (best or {}).get("look", "normal")
