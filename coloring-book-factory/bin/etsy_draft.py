#!/usr/bin/env python3
"""Creates a DRAFT listing in the Etsy shop MySandboxBooks from kit/etsy/listing.json.
Never publishes: there is no call in this file that changes the listing's state. Cleiton is the one who publishes.
Decisions 0004 and 0013. Etsy Open API v3 (official spec read on 22 Nov 2026).

Usage:  etsy_draft.py <book-folder> --dry-run   (validates everything, no network)
        etsy_draft.py <book-folder>             (creates the draft; needs ~/company/.secrets/etsy.json)
"""
import json, mimetypes, os, re, subprocess, sys, urllib.error, urllib.parse, urllib.request, uuid

API = "https://api.etsy.com/v3"
SECRETS = os.path.expanduser("~/company/.secrets/etsy.json")
folder = os.path.abspath(sys.argv[1])
DRY_RUN = "--dry-run" in sys.argv
kit = f"{folder}/kit"
LJ = f"{kit}/etsy/listing.json"
a = json.load(open(LJ))

# 1. Validation with the rules from the official spec
errors = []
t = a["title"]
if len(t) > 140: errors.append("title > 140")
if re.search(r"[^\w\s\.,;:!\?'\"\-\(\)&%+/]", t): errors.append("title has characters outside the rule")
for c in "%:&+":
    if t.count(c) > 1: errors.append(f"title uses '{c}' more than once")
tags = a["tags"]
if len(tags) > 13: errors.append("more than 13 tags")
for g in tags:
    if len(g) > 20 or re.search(r"[^\w\s\-']", g) or "_" in g: errors.append(f"invalid tag: {g}")
price = (a.get("price") or {}).get("eur")
if not price or "approved" not in (a.get("price") or {}).get("state", ""): errors.append("price without Cleiton's approval")
file = f"{kit}/printable.pdf"
if not os.path.exists(file) or os.path.getsize(file) > 20 * 1024 * 1024: errors.append("printable.pdf missing or > 20MB")
photos = []
os.makedirs(f"{kit}/etsy/photos", exist_ok=True)
for i, f in enumerate(a["photos"], 1):
    src, dst = f"{kit}/{f}", f"{kit}/etsy/photos/{i:02d}.jpg"
    if not os.path.exists(src):
        errors.append(f"missing photo: {f}"); continue
    if not os.path.exists(dst):
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "90", "-Z", "2700", src, "--out", dst],
                       check=True, capture_output=True)
    photos.append(dst)
if len(photos) > 20: errors.append("more than 20 photos")
if a.get("listing_id"): errors.append(f"draft {a['listing_id']} already exists; not creating another")
if errors:
    sys.exit("STOPPED:\n- " + "\n- ".join(errors))

body = {"quantity": a.get("quantity", 999), "title": t, "description": a["description"], "price": price,
        "who_made": a.get("who_made", "i_did"), "when_made": a.get("when_made", "2020_2026"), "is_supply": "false",
        "type": "download", "should_auto_renew": "false", "tags": ",".join(tags)}
print(f"OK validation: title {len(t)} chars, {len(tags)} tags, price EUR {price}, {len(photos)} photos, "
      f"PDF {os.path.getsize(file) / 1e6:.1f} MB")
if DRY_RUN:
    print("Dry run: nothing sent to Etsy.\n" + json.dumps({k: v for k, v in body.items() if k != "description"}, indent=1))
    sys.exit(0)

# 2. Access: refresh token (Etsy returns a new one on each use; we save it right away)
s = json.load(open(SECRETS))
r = urllib.request.urlopen(urllib.request.Request(f"{API}/public/oauth/token", data=urllib.parse.urlencode(
    {"grant_type": "refresh_token", "client_id": s["keystring"], "refresh_token": s["refresh_token"]}).encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=30)
tok = json.loads(r.read())
s["refresh_token"] = tok["refresh_token"]
fd = os.open(SECRETS, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, 0o600)
os.write(fd, json.dumps(s).encode()); os.close(fd)
H = {"x-api-key": f"{s['keystring']}:{s['shared_secret']}", "Authorization": f"Bearer {tok['access_token']}"}


def call(method, path, form=None, multipart=None):
    h, data = dict(H), None
    if form is not None:
        h["Content-Type"] = "application/x-www-form-urlencoded"
        data = urllib.parse.urlencode(form).encode()
    if multipart is not None:
        b = uuid.uuid4().hex; parts = []
        for k, v in multipart.items():
            if isinstance(v, tuple):
                name, content = v
                parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
                             f'Content-Type: {mimetypes.guess_type(name)[0] or "application/octet-stream"}\r\n\r\n'.encode() + content + b"\r\n")
            else:
                parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        data = b"".join(parts) + f"--{b}--\r\n".encode()
        h["Content-Type"] = f"multipart/form-data; boundary={b}"
    try:
        with urllib.request.urlopen(urllib.request.Request(API + path, data=data, headers=h, method=method), timeout=300) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"STOPPED: {method} {path} HTTP {e.code}: {e.read().decode()[:400]}")


shop = call("GET", "/application/users/me")["shop_id"]

# 3. Category: looks for "Coloring Books" in the official tree; only continues with exactly 1 result
if not a.get("taxonomy_id"):
    found = []
    def walk(nodes):
        for n in nodes:
            if n.get("name", "").strip().lower() == "coloring books":
                found.append((n["id"], " > ".join(str(x) for x in n.get("full_path_taxonomy_ids", []))))
            walk(n.get("children") or [])
    walk(call("GET", "/application/seller-taxonomy/nodes").get("results", []))
    if len(found) != 1:
        sys.exit(f"STOPPED: category 'Coloring Books' found {len(found)} times: {found}. Pick it by hand.")
    a["taxonomy_id"] = found[0][0]
body["taxonomy_id"] = a["taxonomy_id"]

# 4. Draft + photos + digital file
lst = call("POST", f"/application/shops/{shop}/listings", form=body)
lid = lst["listing_id"]
a["listing_id"] = lid
a["etsy_state"] = "draft created by the bot; Cleiton reviews and publishes"
json.dump(a, open(LJ, "w"), indent=1, ensure_ascii=False)
for i, f in enumerate(photos, 1):
    call("POST", f"/application/shops/{shop}/listings/{lid}/images",
         multipart={"image": (os.path.basename(f), open(f, "rb").read()), "rank": str(i),
                    "alt_text": a.get("photo_alt_texts", ["Coloring book page preview"] * 20)[i - 1] if a.get("photo_alt_texts") else "Cozy coloring book page preview"})
call("POST", f"/application/shops/{shop}/listings/{lid}/files",
     multipart={"file": (f"{a.get('file_name', 'Cozy Little Corners')}.pdf", open(file, "rb").read()),
                "name": f"{a.get('file_name', 'Cozy Little Corners')}.pdf", "rank": "1"})
end = call("GET", f"/application/listings/{lid}")
print(f"Draft created: listing {lid}, state '{end.get('state')}', price {end.get('price')}. "
      f"Review at https://www.etsy.com/your/shops/me/listing-editor/edit/{lid}")
