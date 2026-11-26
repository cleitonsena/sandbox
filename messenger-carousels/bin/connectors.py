"""connectors (26 Nov 2026, decision 0026): publishing for Your Bestie. Standard library only. Keys in chmod 600 files, never printed.

Key files (one value per file, chmod 600, saved by the human):
  ~/.zernio-key          Zernio API key (sk_...)                          -> TikTok, Instagram and image hosting
  ~/.x-ck / ~/.x-cs / ~/.x-at / ~/.x-as   X consumer key/secret, access token/secret (OAuth 1.0a)
Without the key for a network, that network returns state "dry-run" and nothing goes out.

Specification (official docs read on 26 Nov 2026):
  Zernio   https://docs.zernio.com/guides/media-uploads , /posts/create-post , /platforms/tiktok/posts
  X        https://docs.x.com/x-api/media/upload-media , https://docs.x.com/x-api/posts/create-post
NOT VERIFIED until the first real post: Instagram carousel via Zernio; whether
/2/media/upload accepts OAuth 1.0a with the body outside the signature."""
import base64, datetime as dt, hashlib, hmac, json, os, time, urllib.error, urllib.parse, urllib.request, uuid

H = os.path.expanduser
ZB = "https://zernio.com/api/v1"
TIMEZONE = "Europe/Madrid"  # timezone of the machine that runs the cycle; set it to yours


def key(name):
    p = H(f"~/.{name}")
    return open(p).read().strip() if os.path.exists(p) else None


def request(method, url, body=None, headers=None, timeout=120):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            t = r.read()
            return json.loads(t) if t.strip() else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url.split('?')[0]} -> HTTP {e.code}: {e.read()[:400].decode('utf-8', 'replace')}")


# ----------------------------------------------------------------- Zernio (TikTok + hosting)
def _z(method, path, data=None, extra=None):
    k = key("zernio-key")
    hdr = {"Authorization": "Bearer " + k, "Content-Type": "application/json"}; hdr.update(extra or {})
    return request(method, ZB + path, json.dumps(data).encode() if data is not None else None, hdr)


def public_urls(p):
    """uploads the 4 images to Zernio once per post; stores the publicUrl values in the post itself (queue.json)"""
    if p.get("urls"): return p["urls"]
    urls = []
    for f in p["images"]:
        b = open(f, "rb").read()
        r = _z("POST", "/media/presign", {"filename": os.path.basename(f), "contentType": "image/jpeg", "size": len(b)})
        request("PUT", r["uploadUrl"], b, {"Content-Type": "image/jpeg"})
        urls.append(r["publicUrl"])
    p["urls"] = urls
    return urls


def tiktok_account():
    d = _z("GET", "/accounts?platform=tiktok")
    accounts = d.get("accounts") or []
    if not accounts: raise RuntimeError("Zernio has no TikTok account connected")
    return accounts[0]["_id"]


def tiktok(p, when):
    if not key("zernio-key"): return {"state": "dry-run", "note": "no ~/.zernio-key"}
    if dt.datetime.now() > when + dt.timedelta(minutes=30):
        return {"state": "final-error", "note": "time already passed, not publishing late"}
    body = {"content": p["tt_title"][:90],
            "mediaItems": [{"type": "image", "url": u} for u in public_urls(p)],
            "platforms": [{"platform": "tiktok", "accountId": tiktok_account()}],
            "scheduledFor": when.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": TIMEZONE,
            "tiktokSettings": {"privacy_level": "PUBLIC_TO_EVERYONE", "allow_comment": True, "media_type": "photo",
                               "photo_cover_index": 0, "description": p["caption_tt"][:4000], "auto_add_music": True,
                               "content_preview_confirmed": True, "express_consent_given": True, "draft": False}}
    r = _z("POST", "/posts", body, {"Idempotency-Key": str(uuid.uuid5(uuid.NAMESPACE_URL, "carousel-tt-" + p["key"]))})
    post = r.get("post") or {}
    return {"state": "scheduled", "id": post.get("_id", ""), "note": f"zernio {post.get('status', '?')}"}


# ----------------------------------------------------------------- Instagram (via Zernio, second free account; owner's decision 26 Nov)
# https://docs.zernio.com/platforms/instagram/posts and /fields: carousel = several mediaItems; isAiGenerated in platformSpecificData
def instagram(p, when):
    if not key("zernio-key"): return {"state": "dry-run", "note": "no ~/.zernio-key"}
    if dt.datetime.now() > when + dt.timedelta(minutes=30):
        return {"state": "final-error", "note": "time already passed, not publishing late"}
    accounts = _z("GET", "/accounts?platform=instagram").get("accounts") or []
    if not accounts: return {"state": "dry-run", "note": "Zernio has no Instagram account connected"}
    body = {"content": p["caption_ig"][:2200],
            "mediaItems": [{"type": "image", "url": u} for u in public_urls(p)],
            "platforms": [{"platform": "instagram", "accountId": accounts[0]["_id"],
                           "platformSpecificData": {"isAiGenerated": True}}],
            "scheduledFor": when.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": TIMEZONE}
    r = _z("POST", "/posts", body, {"Idempotency-Key": str(uuid.uuid5(uuid.NAMESPACE_URL, "carousel-ig-" + p["key"]))})
    post = r.get("post") or {}
    return {"state": "scheduled", "id": post.get("_id", ""), "note": f"zernio {post.get('status', '?')}"}


# ----------------------------------------------------------------- X (OAuth 1.0a)
def _q(s): return urllib.parse.quote(str(s), safe="~")


def _oauth(method, url):
    ck, cs, at, as_ = (key(f"x-{k}") for k in ("ck", "cs", "at", "as"))
    o = {"oauth_consumer_key": ck, "oauth_nonce": uuid.uuid4().hex, "oauth_signature_method": "HMAC-SHA1",
         "oauth_timestamp": str(int(time.time())), "oauth_token": at, "oauth_version": "1.0"}
    base = "&".join([method, _q(url), _q("&".join(f"{_q(k)}={_q(v)}" for k, v in sorted(o.items())))])
    o["oauth_signature"] = base64.b64encode(hmac.new(f"{_q(cs)}&{_q(as_)}".encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{_q(k)}="{_q(v)}"' for k, v in sorted(o.items()))


def _x_media(f):
    url = "https://api.x.com/2/media/upload"; bd = uuid.uuid4().hex
    body = (f"--{bd}\r\nContent-Disposition: form-data; name=\"media_category\"\r\n\r\ntweet_image\r\n"
            f"--{bd}\r\nContent-Disposition: form-data; name=\"media\"; filename=\"{os.path.basename(f)}\"\r\n"
            f"Content-Type: image/jpeg\r\n\r\n").encode() + open(f, "rb").read() + f"\r\n--{bd}--\r\n".encode()
    r = request("POST", url, body, {"Authorization": _oauth("POST", url), "Content-Type": f"multipart/form-data; boundary={bd}"})
    return r["data"]["id"]


def x(p, when):
    if not all(key(f"x-{k}") for k in ("ck", "cs", "at", "as")):
        return {"state": "dry-run", "note": "no ~/.x-* keys"}
    ids = [_x_media(f) for f in p["images"][:4]]
    url = "https://api.x.com/2/tweets"
    r = request("POST", url, json.dumps({"text": p["x_text"], "media": {"media_ids": ids}, "made_with_ai": True}).encode(),
                {"Authorization": _oauth("POST", url), "Content-Type": "application/json"})
    return {"state": "done", "id": r["data"]["id"]}
