#!/usr/bin/env python3
"""x_pin (26 Nov 2026): gets the X Access Token for the posting account by PIN (OAuth 1.0a, callback "oob").
Reads ~/.x-ck and ~/.x-cs; writes ~/.x-at and ~/.x-as (chmod 600). Never prints keys.
Set the account it must authorize (without @) in X_SCREEN_NAME, then run it in a terminal:
  X_SCREEN_NAME=your_handle python3 bin/x_pin.py     (open the link while logged in AS that account)"""
import base64, hashlib, hmac, os, time, urllib.error, urllib.parse, urllib.request, uuid
H = os.path.expanduser
X_SCREEN_NAME = os.environ.get("X_SCREEN_NAME") or "YOUR_X_HANDLE"  # the only account allowed to be saved
if X_SCREEN_NAME == "YOUR_X_HANDLE":
    raise SystemExit("Set X_SCREEN_NAME to the X account that will post (without @). Nothing saved.")
q = lambda s: urllib.parse.quote(str(s), safe="~")
ck, cs = (open(H(f"~/.x-{k}")).read().strip() for k in ("ck", "cs"))


def signed(url, extra, token_secret=""):
    o = dict(oauth_consumer_key=ck, oauth_nonce=uuid.uuid4().hex, oauth_signature_method="HMAC-SHA1",
             oauth_timestamp=str(int(time.time())), oauth_version="1.0", **extra)
    base = "&".join(["POST", q(url), q("&".join(f"{q(k)}={q(v)}" for k, v in sorted(o.items())))])
    o["oauth_signature"] = base64.b64encode(hmac.new(f"{q(cs)}&{q(token_secret)}".encode(), base.encode(), hashlib.sha1).digest()).decode()
    req = urllib.request.Request(url, data=b"", method="POST",
                                 headers={"Authorization": "OAuth " + ", ".join(f'{q(k)}="{q(v)}"' for k, v in sorted(o.items()))})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return dict(urllib.parse.parse_qsl(r.read().decode()))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")


r = signed("https://api.x.com/oauth/request_token", {"oauth_callback": "oob"})
print(f"\n1. Make sure you are logged in on x.com as @{X_SCREEN_NAME}.")
print("2. Open: https://api.x.com/oauth/authorize?oauth_token=" + r["oauth_token"])
pin = input("3. Authorize and paste the PIN here: ").strip()
a = signed("https://api.x.com/oauth/access_token", {"oauth_token": r["oauth_token"], "oauth_verifier": pin}, r["oauth_token_secret"])
if a.get("screen_name", "").lower() != X_SCREEN_NAME.lower():
    raise SystemExit(f"You authorized @{a.get('screen_name', '?')}, not @{X_SCREEN_NAME}. Nothing saved; repeat logged in to the right account.")
for k, v in (("at", a["oauth_token"]), ("as", a["oauth_token_secret"])):
    p = H(f"~/.x-{k}"); old = os.umask(0o077); open(p, "w").write(v); os.umask(old); os.chmod(p, 0o600)
print(f"Saved. Authorized account: @{a.get('screen_name', '?')}")
