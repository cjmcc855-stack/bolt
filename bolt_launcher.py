#!/usr/bin/env python3
"""
bolt_launcher.py - tiny always-on helper that lets you start/stop Bolt from Discord.
Uses no GPU. Only listens to the owner (HUMAN in creature.py), mapped in names.json.

Discord commands (Caelan only):
  /start   wake Bolt up (refuses if the GPU is still hot)   ('/start bolt' targets him by name)
  /stop    put Bolt to sleep and unload the model
  /status  is he running, GPU temp, overheat lock?

Run it by double-clicking. Leave its window open (minimized is fine).
"""
import json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
BOLT = os.path.join(HERE, "creature.py")


def _setting(key, default):
    """Reads NAME / HUMAN straight out of creature.py, so renaming the creature or owner there is enough."""
    try:
        with open(BOLT, encoding="utf-8") as f:
            hit = re.search(rf'^{key}\s*=\s*"([^"]+)"', f.read(), re.M)
        return hit.group(1) if hit else default
    except OSError:
        return default


OWNER, CREATURE = _setting("HUMAN", "Caelan"), _setting("NAME", "Bolt")
RESUME_TEMP = 60          # degC: GPU must be under this before /start will wake him after an overheat
LOCK_FILE, ALIVE_FILE, STOP_FLAG = "overheat.lock", "bolt.alive", "stop.flag"
API = "https://discord.com/api/v10"

with open("discord_config.json", encoding="utf-8") as f:
    CFG = json.load(f)
CID = CFG["channel_id"]
NAMES = {k.lower(): v for k, v in CFG.get("names", {}).items()}
try:                                   # names.json (no secrets) adds to / overrides the config's names
    with open("names.json", encoding="utf-8") as f:
        NAMES.update({k.lower(): v for k, v in json.load(f).items()})
except (FileNotFoundError, ValueError):
    pass


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def req(method, path, body=None):
    h = {"Authorization": f"Bot {CFG['token']}", "User-Agent": "DiscordBot (bolt-launcher, 1.0)",
         "Content-Type": "application/json"}
    r = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None, method=method, headers=h)
    with urllib.request.urlopen(r, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def say(text):
    print(f"[{now()}] {text}")
    try:
        req("POST", f"/channels/{CID}/messages", {"content": f"🛠️ {text}"})
    except Exception as e:
        print(f"  (couldn't post: {e})")


def gpu_temp():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
        return max(int(x) for x in out.split())
    except Exception:
        return None


def bolt_alive():
    if os.path.exists(LOCK_FILE):      # a lock means he shut himself down
        return False
    try:
        with open(ALIVE_FILE) as f:
            return time.time() - float(f.read()) < 30
    except Exception:
        return False


def do_status():
    t = gpu_temp()
    lock = open(LOCK_FILE).read().strip() if os.path.exists(LOCK_FILE) else None
    say(f"Bolt is {'awake' if bolt_alive() else 'asleep'}. GPU {t if t is not None else '?'}C."
        + (f" Overheat lock: {lock}." if lock else ""))


def do_start():
    if bolt_alive():
        return say("Bolt's already awake.")
    t = gpu_temp()
    locked = os.path.exists(LOCK_FILE)
    if locked and (t is None or t >= RESUME_TEMP):
        return say(f"Not starting. He shut down for overheating and the GPU is at {t}C. "
                   f"Needs to be under {RESUME_TEMP}C. Try again in a bit.")
    if os.path.exists(STOP_FLAG):
        os.remove(STOP_FLAG)
    args = [sys.executable, BOLT] + (["--cleared"] if locked else [])
    subprocess.Popen(args, cwd=HERE, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    time.sleep(20)
    say("Bolt is waking up." + (" Overheat lock cleared." if locked else "") if bolt_alive()
        else "Tried to start Bolt but he didn't come up. Check the PC (is Ollama running?).")


def do_stop():
    if not bolt_alive():
        return say("Bolt's already asleep.")
    open(STOP_FLAG, "w").close()
    for _ in range(12):
        time.sleep(5)
        if not bolt_alive():
            return say("Bolt's asleep. Model unloaded from the GPU.")
    say("Asked Bolt to stop but he hasn't confirmed yet. He'll stop within a minute.")


def main():
    print(f"{CREATURE} launcher running. Commands in Discord ({OWNER} only): !start  !stop  !status  "
          f"(add a name, like !stop {CREATURE.lower()}, when other creatures share the channel)")
    print("Leave this window open. It doesn't use the GPU.\n")
    try:
        latest = req("GET", f"/channels/{CID}/messages?limit=1")
        last = latest[0]["id"] if latest else "0"
    except Exception as e:
        print(f"Discord connection failed: {e}")
        input("Press Enter to close...")
        return
    while True:
        time.sleep(10)
        try:
            msgs = req("GET", f"/channels/{CID}/messages?after={last}&limit=20") or []
        except Exception as e:
            print(f"  (Discord read hiccup: {e})")
            time.sleep(30)
            continue
        for m in sorted(msgs, key=lambda m: int(m["id"])):
            last = m["id"]
            if m["author"].get("bot"):
                continue
            cmd, _, target = (m.get("content") or "").strip().lower().partition(" ")
            if cmd.startswith("!"):
                cmd = "/" + cmd[1:]
            target = target.strip().strip("@,:")
            who = NAMES.get(m["author"]["username"].lower())
            if cmd not in ("/start", "/stop", "/status") or (target and target != CREATURE.lower()):
                continue                       # '!stop spike' is for Spike's launcher
            if who != OWNER:
                if target:                     # only speak up when they named this creature; others may share the channel
                    say(f"Only {OWNER} can do that for {CREATURE}.")
                continue
            {"/start": do_start, "/stop": do_stop, "/status": do_status}[cmd]()


if __name__ == "__main__":
    main()
