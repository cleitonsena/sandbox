#!/usr/bin/env python3
"""Generates a coloring page via the OpenAI Images API (decision 0007).
Usage: generate_image.py MODEL QUALITY OUTPUT.png "prompt"
The key lives in ~/.openai-images (chmod 600) and is never printed."""
import base64, json, os, sys, time, urllib.error, urllib.request

model, quality, out, prompt = sys.argv[1:5]
with open(os.path.expanduser("~/.openai-images")) as f:
    key = f.read().strip()
body = json.dumps({"model": model, "prompt": prompt, "n": 1,
                   "size": os.environ.get("SIZE") or "1024x1536", "quality": quality}).encode()
req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=body,
                             headers={"Content-Type": "application/json",
                                      "Authorization": "Bearer " + key})
del key
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read())
except urllib.error.HTTPError as e:
    print(json.dumps({"model": model, "quality": quality, "error": e.code,
                      "detail": e.read()[:400].decode("utf-8", "replace")}))
    sys.exit(1)
secs = round(time.time() - t0, 1)
with open(out, "wb") as f:
    f.write(base64.b64decode(d["data"][0]["b64_json"]))
print(json.dumps({"model": model, "quality": quality, "seconds": secs,
                  "file": out, "usage": d.get("usage")}))
