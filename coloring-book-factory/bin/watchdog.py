#!/usr/bin/env python3
"""Factory watchdog (Cleiton's request, 23 Nov 2026). No AI, zero cost. Runs every 30 minutes (launchd).

Ladder: 1) automatic rules (the factory already waits on its own for the Apify reset);
        2) MausBot gets the error and tries to fix it;
        3) Cleiton only gets what MausBot cannot fix or what is his decision.

Checks: Apify balance, queue tasks in error, error gates, repeated failures in the log, stopped factory.
Each alert has a key; the same key is never sent twice (state in ~/company/watchdog.json + --send-id).
Usage: watchdog.py [--dry-run]"""
import glob, hashlib, json, os, re, subprocess, sys, time, urllib.request

H = os.path.expanduser
COMPANY, BOOKS = H("~/company"), H("~/books")
STATE = f"{COMPANY}/watchdog.json"
FACTORY_LOG, PENDING, REPORT = f"{BOOKS}/factory.log", f"{COMPANY}/decisions/pending.md", f"{COMPANY}/reports/factory.md"
APP = H("~/Applications/OpenMausBot.app/Contents/MacOS/OpenMausBot")
JS = H("~/Applications/OpenMausBot.app/Contents/Resources/server/openmausbot.js")
TOKEN, URL = H("~/.openmausbot-watchdog-token"), "http://127.0.0.1:8799"
DRY = "--dry-run" in sys.argv
STOPPED_HOURS, REPEATS = 2, 3

RULES = (
    "\n\nWhat to do (you are the supervisor; Cleiton only steps in as a last resort):\n"
    "1. Diagnose: read ~/books/factory.log, the task file in ~/company/queue/ and the code in ~/books/bin/ if needed.\n"
    "2. If you can fix it without spending money, without creating accounts, without publishing, without deleting and without touching keys "
    "or passwords, fix it. Examples: reset a task's state so it tries again, fix a data file.\n"
    "3. Write one line at the end of ~/company/log.md: date, the error, what you did.\n"
    "4. If you cannot, or if the decision belongs to the board (money, accounts, publishing, deleting, changing rules), "
    "do nothing and reply starting with 'FOR CLEITON:' with the problem and the question in one sentence each.\n"
    "Never change the factory code without Cleiton's approval."
)


def lj(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d


def now():
    return time.strftime("%Y-%m-%d %H:%M")


def send(key, title, text, state):
    if key in state["sent"]:
        return False
    msg = f"[Watchdog {now()}] {title}\n\n{text}"
    sid = "watchdog-" + hashlib.sha1(key.encode()).hexdigest()[:16]
    cmd = ["env", "ELECTRON_RUN_AS_NODE=1", APP, JS, "send", "MausBot", "--task", "new", "--title", f"Watchdog: {title}"[:80],
           "--text", msg, "--send-id", sid, "--url", URL, "--token-file", TOKEN, "--quiet"]
    if DRY:
        cmd.append("--dry-run")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    ok = r.returncode == 0
    print(now(), "send", key, "ok" if ok else f"FAILED {r.returncode}: {(r.stderr or r.stdout)[-300:]}", flush=True)
    if ok and not DRY:
        state["sent"][key] = now()
    return ok


def apify(state):
    try:
        k = open(H("~/.apify-personal")).read().strip()
        req = urllib.request.Request("https://api.apify.com/v2/users/me/limits", headers={"Authorization": "Bearer " + k})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)["data"]
    except Exception as e:
        print(now(), "apify: could not read", str(e)[:200], flush=True)
        return
    used, maximum = d["current"]["monthlyUsageUsd"], d["limits"]["maxMonthlyUsageUsd"]
    cycle, end = d["monthlyUsageCycle"]["startAt"][:10], d["monthlyUsageCycle"]["endAt"][:10]
    state["apify"] = {"used": round(used, 3), "max": maximum, "cycle_end": end, "read": now()}
    base = f"Apify (personal account): US$ {used:.2f} of {maximum:.2f} in the cycle that ends on {end} (UTC)."
    if used >= maximum - 0.01:
        send(f"apify-100-{cycle}", "Apify out of balance", base + "\nNothing to do: the factory no longer calls Apify "
             "and the tasks stay 'waiting' until the reset. Just so you know. Do not upgrade or pay for anything. "
             "Reply only 'OK, seen.'", state)
    elif used >= 0.8 * maximum:
        send(f"apify-80-{cycle}", "Apify at 80%", base + "\nJust so you know: when it runs out, the factory waits on its own "
             "for the reset. Reply only 'OK, seen.'", state)


def queue_errors(state):
    for f in sorted(glob.glob(f"{COMPANY}/queue/*.json")):
        t = lj(f, {}) or {}
        if t.get("state") == "error" and t.get("error"):
            name = os.path.basename(f)[:-5]
            h = hashlib.sha1(t["error"].encode()).hexdigest()[:8]
            send(f"error-{name}-{h}", f"task {name} in error",
                 f"The factory stopped on task {name} (file {f}).\nError: {t['error']}" + RULES, state)


def error_gates(state):
    try:
        txt = open(PENDING).read()
    except Exception:
        return
    for m in re.finditer(r"^- \*\*(.+?)\*\* \[error\]: (.+)$", txt, re.M):
        if os.path.exists(f"{COMPANY}/queue/{m.group(1)}.json"):
            continue  # already handled in queue_errors
        h = hashlib.sha1(m.group(2).encode()).hexdigest()[:8]
        send(f"gate-{m.group(1)}-{h}", f"error in {m.group(1)}", f"Factory error gate: {m.group(2)}" + RULES, state)


def repeated_failures(state):
    try:
        lines = open(FACTORY_LOG).read().splitlines()[-2000:]
    except Exception:
        return
    count = {}
    for l in lines:
        m = re.match(r"^\d\d:\d\d:\d\d (\S+)(?: (\S+))? (?:failed|could not)(.*)$", l)
        if m:
            k = (m.group(1), m.group(2) or "-")
            count[k] = (count.get(k, (0, ""))[0] + 1, m.group(3).strip()[:300])
    day = time.strftime("%Y-%m-%d")
    for (task, step), (n, last) in count.items():
        if n >= REPEATS:
            send(f"failure-{task}-{step}-{day}", f"{step} fails in {task}",
                 f"Step '{step}' of task {task} failed {n} times in the factory log. The factory does not stop because of it, "
                 f"but the step does not get done.\nLast message: {last}" + RULES, state)


def factory_stopped(state):
    try:
        age = (time.time() - os.path.getmtime(REPORT)) / 3600
    except Exception:
        return
    if os.path.exists(f"{BOOKS}/.factory.lock") and age < 6:
        return  # running a long step (images, Apify)
    if age > STOPPED_HOURS:
        r = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/com.example.factory"], capture_output=True, text=True)
        info = " ".join(l.strip() for l in r.stdout.splitlines() if "state" in l or "last exit" in l or "runs" in l)[:300]
        send(f"stopped-{time.strftime('%Y-%m-%d')}", "factory stopped",
             f"The factory has not updated ~/company/reports/factory.md for {age:.1f} hours (it should every 30 min).\n"
             f"launchd: {info or 'no information'}\nLast lines: ~/books/factory.log." + RULES, state)


def main():
    state = lj(STATE, {}) or {}
    state.setdefault("sent", {})
    for f in (apify, queue_errors, error_gates, repeated_failures, factory_stopped):
        try:
            f(state)
        except Exception as e:  # one failed check does not stop the others
            print(now(), "ERROR", f.__name__, str(e)[:300], flush=True)
    cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - 60 * 86400))
    state["sent"] = {k: v for k, v in state["sent"].items() if v[:10] >= cutoff}
    state["last_round"] = now()
    if not DRY:
        json.dump(state, open(STATE, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
