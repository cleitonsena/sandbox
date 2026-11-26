#!/usr/bin/env python3
"""reassess: judges the pages in the human queue again WITHOUT generating new images (Cleiton, 25 Nov 2026).
The gray limit goes up from 6% to LIMIT (the other check rules stay the same); the ones that pass go to the reviewer.
Usage (inside the book folder): python3 reassess.py [0.09]
"""
import json, os, sys

LIMIT = float(sys.argv[1]) if len(sys.argv) > 1 else 0.09
src = open(os.path.expanduser("~/books/bin/page_line.py")).read()
cut = src.index('if sys.argv[1] == "--check"')
sys.argv = ["page_line.py", "--functions-only"]  # folder = cwd; generates nothing
g = {"__name__": "page_line_functions"}
exec(compile(src[:cut], "page_line.py", "exec"), g)
from PIL import Image

book = json.load(open("book.json"))
themes = {p["id"]: p["theme"] for p in book["pages"]}
state = g["state"]


def gray(f):
    im = Image.open(f).convert("L"); h = im.histogram()
    return sum(h[40:216]) / (im.size[0] * im.size[1])


res = {"approved": [], "remaining": []}
for pid, st in sorted(state.items()):
    if st.get("state") != "human_queue":
        continue
    atts = [t for t in st["attempts"] if os.path.exists(t.get("file", ""))]
    atts.sort(key=lambda t: gray(t["file"]))
    reas = []
    for t in atts:
        c = gray(t["file"])
        probs = [p for p in g["check"](t["file"]) if not p.startswith("too much gray")]
        if c > LIMIT:
            probs.append(f"gray {c:.1%} > {LIMIT:.0%}")
        if probs:
            reas.append({"attempt": t["n"], "gray": round(c, 3), "stage": "check", "problems": probs})
            continue
        rv = g["reviewer"](t["file"], themes[pid])
        reas.append({"attempt": t["n"], "gray": round(c, 3), "stage": "reviewer", "reviewer": rv})
        print(pid, "t", t["n"], f"gray {c:.1%}", "OK" if rv.get("approved") else "FAIL", rv.get("problems", [])[:2], flush=True)
        if rv.get("approved"):
            g["upscale"](t["file"], os.path.join("final", pid + ".png"))
            st["state"] = "approved"
            st["approved_in_reassessment"] = {"attempt": t["n"], "gray_limit": LIMIT, "date": "2026-11-25"}
            break
    st["reassessment"] = reas
    g["save"]()
    (res["approved"] if st["state"] == "approved" else res["remaining"]).append(pid)
    if st["state"] != "approved":
        print(pid, "stays in the queue", [r.get("problems") or r.get("reviewer", {}).get("problems") for r in reas][:3], flush=True)
print("SUMMARY", json.dumps(res))
