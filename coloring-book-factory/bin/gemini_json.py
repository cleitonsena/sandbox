#!/usr/bin/env python3
"""Text fallback for the factory (Cleiton's request, 23 Nov 2026): when Codex fails, the same request goes to free Gemini.
Runs in the venv ~/.venv-genai (official google-genai SDK). Key in ~/.gemini-personal, never printed.
Codex reads files on its own; Gemini does not. So this script appends the files the request mentions.
Public data only: the free Gemini plan trains on what it receives.
Usage: gemini_json.py --request FILE --schema FILE --output FILE --cwd DIR [--img FILE ...]"""
import argparse, glob, json, os, re, sys, time, warnings
warnings.filterwarnings("ignore")
from google import genai
from google.genai import types

MODELS = ["gemini-flash-lite-latest", "gemini-flash-latest"]
PER_FILE, TOTAL = 60_000, 400_000  # characters

ap = argparse.ArgumentParser()
ap.add_argument("--request", required=True); ap.add_argument("--schema", required=True)
ap.add_argument("--output", required=True); ap.add_argument("--cwd", required=True)
ap.add_argument("--img", action="append", default=[])
a = ap.parse_args()
request, schema = open(a.request).read(), json.load(open(a.schema))


def files(text, cwd):
    """Paths the request mentions (x.md, x.json, x.log, folder/ and globs), resolved against cwd and ~."""
    found = []
    for tok in re.findall(r"[~\w./*-]+(?:\.(?:md|json|log|txt|csv)|/)", text):
        tok = tok.rstrip(".,;:)")
        base = os.path.expanduser(tok) if tok.startswith("~") else os.path.join(cwd, tok)
        if tok.endswith("/") and os.path.isdir(base):  # folder: the 5 most recent text files
            fs = [f for f in glob.glob(base + "*") if os.path.isfile(f) and f.endswith((".md", ".json", ".log", ".txt", ".csv"))]
            found += sorted(fs, key=os.path.getmtime, reverse=True)[:5]
        else:
            found += [f for f in glob.glob(base) if os.path.isfile(f)]
    seen, out = set(), []
    for f in found:
        r = os.path.realpath(f)
        if r not in seen and not os.path.basename(r).startswith("."):
            seen.add(r); out.append(r)
    return out


attachments, total = [], 0
for f in files(request, a.cwd):
    txt = open(f, errors="replace").read()
    if len(txt) > PER_FILE:
        txt = txt[:PER_FILE] + "\n[... truncated ...]"
    if total + len(txt) > TOTAL:
        break
    total += len(txt)
    attachments.append(f"\n\n===== FILE {f} =====\n{txt}")
text = request + ("\n\nContents of the referenced files (already read for you):" + "".join(attachments) if attachments else "")
parts = [types.Part.from_bytes(data=open(i, "rb").read(), mime_type="image/png" if i.endswith(".png") else "image/jpeg")
         for i in a.img] + [text]

c = genai.Client(api_key=open(os.path.expanduser("~/.gemini-personal")).read().strip(),
                 http_options=types.HttpOptions(timeout=180_000))
cfg = types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema)
errors = []
for m in MODELS:
    t = time.time()
    try:
        r = c.models.generate_content(model=m, contents=parts, config=cfg)
        d = json.loads(r.text)
        missing = [k for k in schema.get("required", []) if k not in d]
        if missing:
            raise ValueError(f"missing fields {missing}")
        json.dump(d, open(a.output, "w"), ensure_ascii=False, indent=1)
        print(json.dumps({"model": m, "seconds": round(time.time() - t), "files": len(attachments),
                          "tokens": getattr(r.usage_metadata, "total_token_count", None)}))
        sys.exit(0)
    except Exception as e:
        errors.append(f"{m}: {str(e)[:200]}")


def groq():
    """3rd step (Cleiton, 24 Nov 2026): free Groq, openai/gpt-oss-120b. Free plan limits (official page):
    30 requests/min, 1000/day, 8000 tokens/min. Text only (no images) and small requests only.
    Key in ~/.groq, never printed."""
    import urllib.error, urllib.request
    kf = os.path.expanduser("~/.groq")
    if a.img or not os.path.exists(kf):
        return "groq: no key" if not a.img else "groq: request has images"
    if len(text) / 3.5 > 4500:
        return f"groq: request too large for the free plan (~{int(len(text) / 3.5)} tokens)"
    k = open(kf).read().strip()
    for strict in (True, False):
        body = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": text}],
                "max_completion_tokens": 3000,
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "output", "strict": strict, "schema": schema}}}
        req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", json.dumps(body).encode(),
                                     {"Authorization": "Bearer " + k, "Content-Type": "application/json",
                                      "User-Agent": "factory/1.0"})
        t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                resp = json.load(r)
            d = json.loads(resp["choices"][0]["message"]["content"])
            missing = [c for c in schema.get("required", []) if c not in d]
            if missing:
                raise ValueError(f"missing fields {missing}")
            json.dump(d, open(a.output, "w"), ensure_ascii=False, indent=1)
            print(json.dumps({"model": "groq/gpt-oss-120b", "strict": strict, "seconds": round(time.time() - t),
                              "tokens": (resp.get("usage") or {}).get("total_tokens")}))
            sys.exit(0)
        except urllib.error.HTTPError as e:
            msg = f"groq HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
            if e.code != 400:
                return msg
        except Exception as e:
            msg = f"groq: {str(e)[:200]}"
    return msg


def zai():
    """4th step (Cleiton, 24 Nov 2026): Z.ai GLM-4.7-Flash, "Completely Free" (docs.z.ai), 200K context, text only.
    Only has json_object mode (no strict schema): the schema goes in the request and required fields are checked here.
    Key in ~/.zai, never printed. Free plan usage limits: not published (NV)."""
    import urllib.error, urllib.request
    kf = os.path.expanduser("~/.zai")
    if a.img or not os.path.exists(kf):
        return "zai: no key" if not a.img else "zai: request has images"
    k = open(kf).read().strip()
    msg = "zai: no attempt"
    prompt = (text + "\n\nAnswer ONLY with a valid JSON object that follows exactly this JSON Schema "
              "(every field in 'required' is mandatory):\n" + json.dumps(schema, ensure_ascii=False))
    for attempt in (1, 2):
        body = {"model": "glm-4.7-flash", "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"}}
        req = urllib.request.Request("https://api.z.ai/api/paas/v4/chat/completions", json.dumps(body).encode(),
                                     {"Authorization": "Bearer " + k, "Content-Type": "application/json",
                                      "User-Agent": "factory/1.0"})
        t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.load(r)
            d = json.loads(resp["choices"][0]["message"]["content"])
            missing = [c for c in schema.get("required", []) if c not in d]
            if missing:
                raise ValueError(f"missing fields {missing}")
            json.dump(d, open(a.output, "w"), ensure_ascii=False, indent=1)
            print(json.dumps({"model": "zai/glm-4.7-flash", "attempt": attempt, "seconds": round(time.time() - t),
                              "tokens": (resp.get("usage") or {}).get("total_tokens")}))
            sys.exit(0)
        except urllib.error.HTTPError as e:
            return f"zai HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
        except Exception as e:
            msg = f"zai: {str(e)[:200]}"
    return msg


errors.append(groq())
errors.append(zai())
sys.exit("gemini, groq and zai failed: " + " | ".join(errors))
