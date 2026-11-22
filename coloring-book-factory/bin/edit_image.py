#!/usr/bin/env python3
"""Edits/upscales an image via the OpenAI Images API (edits endpoint).
Usage: edit_image.py MODEL QUALITY SIZE INPUT.png OUTPUT.png "prompt"
The key lives in ~/.openai-images (chmod 600) and is never printed."""
import base64, json, os, sys, time, urllib.error, urllib.request, uuid

model, quality, size, src, out, prompt = sys.argv[1:7]
with open(os.path.expanduser("~/.openai-images")) as f:
    key = f.read().strip()
b = uuid.uuid4().hex
parts = []
for k, v in [("model", model), ("quality", quality), ("size", size), ("prompt", prompt)]:
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
parts.append(f'--{b}\r\nContent-Disposition: form-data; name="image[]"; filename="in.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
             + open(src, "rb").read() + b"\r\n")
parts.append(f"--{b}--\r\n".encode())
req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=b"".join(parts),
                             headers={"Content-Type": f"multipart/form-data; boundary={b}",
                                      "Authorization": "Bearer " + key})
del key
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
except urllib.error.HTTPError as e:
    print(json.dumps({"error": e.code, "detail": e.read()[:400].decode("utf-8", "replace")}))
    sys.exit(1)
with open(out, "wb") as f:
    f.write(base64.b64decode(d["data"][0]["b64_json"]))
print(json.dumps({"seconds": round(time.time() - t0, 1), "file": out, "usage": d.get("usage")}))
