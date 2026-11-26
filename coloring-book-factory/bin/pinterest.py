#!/usr/bin/env python3
"""pinterest (26 Nov 2026): Pinterest OAuth 2.0 login and manual publishing of a book's pins. Standard library only, Python 3.9.

Two jobs: (1) the screen recording that Pinterest asks for before granting Standard access (it must show the
OAuth flow and one real API action); (2) later, publishing the pins that promote.py left in
<book>/kit/pinterest/pins.json. It is NOT wired into the factory: publishing on Pinterest stays a human step.

Official docs read on 26 Nov 2026:
  https://developers.pinterest.com/docs/getting-started/set-up-authentication-and-authorization/
  https://developers.pinterest.com/docs/key-concepts/access-tiers/
  https://developers.pinterest.com/docs/api/v5/pins-create/  and  /boards-list/

Key files (chmod 600, never printed):
  ~/.pinterest-app-id    app ID from My apps
  ~/.pinterest-secret    app secret (only shown in My apps once the app has Trial access)
  ~/.pinterest-token     written by "connect": JSON with access_token and refresh_token

Usage:
  pinterest.py connect             opens the OAuth page in the browser, receives the code, swaps it for a token
  pinterest.py refresh             renews the access token (do it within 30 days)
  pinterest.py me                  GET /v5/user_account (prints the username only)
  pinterest.py boards              lists boards (name and id)
  pinterest.py publish BOOK N      publishes pin N (1..5) from the book's pins.json
  --sandbox                        uses api-sandbox.pinterest.com (test pins)

NOT VERIFIED until first real use: whether Pinterest accepts an http://localhost redirect with a port; whether
ai_disclosures takes any value besides AI_MODIFIED (so it is not sent: the AI disclosure is in the pin
description, as promote.py writes it)."""
import base64, http.server, json, os, secrets, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

H = os.path.expanduser
REDIRECT = os.environ.get("PINTEREST_REDIRECT", "http://localhost:8085/")
SCOPES = "user_accounts:read,boards:read,pins:read,pins:write"
TOKEN_F = H("~/.pinterest-token")
BOOKS = H(os.environ.get("BOOKS_DIR", "~/books"))
SANDBOX = "--sandbox" in sys.argv
API = "https://api-sandbox.pinterest.com/v5" if SANDBOX else "https://api.pinterest.com/v5"


def key(name):
    p = H(f"~/.{name}")
    if not os.path.exists(p):
        sys.exit(f"Missing ~/.{name}. Save it in a chmod 600 file first.")
    return open(p).read().strip()


def request(method, url, body=None, headers=None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            t = r.read()
            return json.loads(t) if t.strip() else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {url.split('?')[0]} -> HTTP {e.code}: {e.read()[:400].decode('utf-8', 'replace')}")


def token_post(data):
    basic = base64.b64encode(f"{key('pinterest-app-id')}:{key('pinterest-secret')}".encode()).decode()
    r = request("POST", API + "/oauth/token", urllib.parse.urlencode(data).encode(),
                {"Authorization": "Basic " + basic, "Content-Type": "application/x-www-form-urlencoded"})
    r["obtained_at"] = int(time.time())
    fd = os.open(TOKEN_F, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(r, f)
    os.chmod(TOKEN_F, 0o600)
    print(f"Token saved to {TOKEN_F} (chmod 600). Scopes: {r.get('scope')}. "
          f"Expires in {r.get('expires_in', 0) // 86400} days. The value is not shown.")


def receive_code():
    """one-shot local server on the REDIRECT port; with no port, asks you to paste the URL"""
    u = urllib.parse.urlparse(REDIRECT)
    if not u.port:
        url = input("Paste the URL Pinterest sent you to: ").strip()
        return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    box = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            box.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write("<h2>Pin Publisher: authorization received.</h2>"
                             "<p>You can close this tab and go back to the terminal.</p>".encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", u.port), Handler)
    while "code" not in box and "error" not in box:
        srv.handle_request()
    return box


def connect():
    key("pinterest-secret")
    state = secrets.token_urlsafe(16)
    url = "https://www.pinterest.com/oauth/?" + urllib.parse.urlencode(
        {"client_id": key("pinterest-app-id"), "redirect_uri": REDIRECT, "response_type": "code",
         "scope": SCOPES, "state": state})
    print("1. Opening the Pinterest authorization page in the browser.")
    print(f"   Scopes requested: {SCOPES}")
    subprocess.run(["open", url])
    q = receive_code()
    if "error" in q:
        sys.exit(f"Pinterest returned an error: {q['error'][0]}")
    if q.get("state", [""])[0] != state:
        sys.exit("state does not match: stopping (possible CSRF).")
    print("2. Code received and state matches. Swapping the code for a token (HTTP Basic with app ID and secret).")
    token_post({"grant_type": "authorization_code", "code": q["code"][0], "redirect_uri": REDIRECT})


def tok():
    if not os.path.exists(TOKEN_F):
        sys.exit("No token. Run first: pinterest.py connect")
    return json.load(open(TOKEN_F))


def refresh():
    token_post({"grant_type": "refresh_token", "refresh_token": tok()["refresh_token"]})


def api(method, path, data=None):
    headers = {"Authorization": "Bearer " + tok()["access_token"], "Content-Type": "application/json"}
    return request(method, API + path, json.dumps(data).encode() if data is not None else None, headers)


def boards():
    out, mark = {}, None
    while True:
        r = api("GET", "/boards?page_size=250" + (f"&bookmark={urllib.parse.quote(mark)}" if mark else ""))
        for b in r.get("items", []):
            out[b["name"]] = b["id"]
        mark = r.get("bookmark")
        if not mark:
            return out


def publish(book, n):
    folder = os.path.join(BOOKS, book, "kit", "pinterest")
    pins = json.load(open(os.path.join(folder, "pins.json")))
    p = pins[n - 1]
    b = boards()
    if p["board"] not in b:
        sys.exit(f"Board '{p['board']}' does not exist on the account. Create it on Pinterest and run again.")
    img = os.path.join(folder, p["image"])
    body = {"board_id": b[p["board"]], "title": p["title"][:100], "description": p["description"][:800],
            "link": p["link"], "alt_text": p["alt"][:500],
            "media_source": {"source_type": "image_base64", "content_type": "image/png",
                             "data": base64.b64encode(open(img, "rb").read()).decode()}}
    print(f"Publishing pin {n}/{len(pins)}: '{p['title']}' on board '{p['board']}'.")
    r = api("POST", "/pins", body)
    print(f"Pin created: id {r.get('id')}  https://www.pinterest.com/pin/{r.get('id')}/")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    cmd = a[0] if a else ""
    if cmd == "connect": connect()
    elif cmd == "refresh": refresh()
    elif cmd == "me": print("Connected account:", api("GET", "/user_account").get("username"))
    elif cmd == "boards":
        for name, i in boards().items(): print(f"{i}  {name}")
    elif cmd == "publish" and len(a) == 3: publish(a[1], int(a[2]))
    else: print(__doc__)
