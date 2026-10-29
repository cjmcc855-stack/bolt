#!/usr/bin/env python3
"""
world_test.py - Bolt's real code living in the real shared town (shasta-world), started in test mode, next to a
scripted Spike. Needs a copy of the shasta-world repo:

    python tests/world_test.py path/to/shasta-world [path/to/bolt_folder]

Checks: the switch, moving, talking with Spike at human speed, Caelan's !leave reserved for Bolt, gifts from
Spike, Spike's fir, the town going away and coming back, roosting, and a crash mid-reply. Without a shasta-world
path it says so and passes, so it can sit in a folder without the server. Ends with PROBLEMS: 0.
"""
import importlib.util, json, os, shutil, socket, sys, tempfile, time, urllib.request

if len(sys.argv) < 2 or not os.path.isfile(os.path.join(sys.argv[1], "world", "server.py")):
    print("skipped: give the path to a shasta-world checkout to run this one\n\nPROBLEMS: 0")
    sys.exit(0)
SW = os.path.abspath(sys.argv[1])
SRC = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), ".."))
WORK = tempfile.mkdtemp(prefix="bolt_world_")
for f in os.listdir(SRC):
    if f.endswith(".py"):
        shutil.copy(os.path.join(SRC, f), os.path.join(WORK, f))
os.chdir(WORK)
sys.path[:0] = [WORK, SW]
from world.server import Server, World, TEST_ROSTER          # noqa: E402  (Elliott's server, test mode)
from world_client import WorldClient                         # noqa: E402

spec = importlib.util.spec_from_file_location("creature", "creature.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
c.DISCORD = {}
c.real_weather = lambda: {"kind": "clear", "temp_f": 50, "wind_mph": 3, "real": False}
c.is_night = lambda: False
POSTS, PROMPTS, PROBLEMS = [], [], []
c.discord_post = lambda text, file=None: POSTS.append(text)
PLAN = {"action": "think", "target": "", "broken": False}


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        PROBLEMS.append(what)


def brain(prompt, json_mode=True, temp=0.9, **kw):
    PROMPTS.append(prompt)
    if "just said this to you" in prompt or "Just said to you" in prompt:
        if PLAN["broken"]:
            raise ConnectionError("brain hiccup (test)")
        return "Kraa. Hey Spike."
    if '"action"' in prompt:
        return json.dumps({"thought": "hm", "action": PLAN["action"], "target": PLAN["target"]})
    if "How did it honestly make you feel" in prompt:
        return json.dumps({"feeling": 0, "reflection": "fine"})
    return "{}"


c.call_llm = brain
port = (lambda so: (so.bind(("127.0.0.1", 0)), so.getsockname()[1], so.close())[1])(socket.socket())
DB = os.path.join(WORK, "world.db")
URL = f"http://127.0.0.1:{port}"
SERVER = {"s": None, "up": False}


def up():
    SERVER["s"] = Server(World(DB, TEST_ROSTER, test=True), port=port, background=False).start()
    SERVER["up"] = True


def down():
    SERVER["s"].stop()
    SERVER["up"] = False


up()
spike, sws = WorldClient(URL, TEST_ROSTER["spike"]["token"], "spike", timeout=1.0, retry=(0, 0)), {}


def spike_sees():
    return {h["id"]: h for h in (spike.look(sws, sws.get("place", "fir"), True) or {}).get("here", [])}


def spike_go(place):
    sws["place"] = place
    spike.look(sws, place, True)
    spike.queue(sws, "go", to=place)
    spike.send(sws)


def advance(seconds):
    req = urllib.request.Request(URL + "/v1/_test", data=json.dumps({"advance": seconds}).encode(), method="POST")
    urllib.request.urlopen(req, timeout=5).read()


def turn(action="think", target=""):
    """One of his turns. They're 5 minutes apart on the PC, so the town's clock moves 5 minutes too."""
    global s
    if SERVER["up"]:
        advance(300)
    PLAN.update(action=action, target=target)
    s = c.run_tick(s)
    c.send_outbox(s)


def hoard(name):
    c.HOARD = None
    return sum(v["count"] for k, v in c.hoard()["items"].items() if k.startswith(name))


print("1. the switch")
check(isinstance(c.make_town(), c.LocalTown) and not isinstance(c.make_town(), c.WorldTown), "no world_config.json: his own town")
with open(c.WORLD_CONFIG, "w") as f:
    json.dump({"enabled": False, "url": URL, "token": "x" * 30}, f)
check(not isinstance(c.make_town(), c.WorldTown), "enabled: false: his own town")
with open(c.WORLD_CONFIG, "w") as f:
    json.dump({"enabled": True, "url": URL, "token": "short"}, f)
check(not isinstance(c.make_town(), c.WorldTown), "a missing or too-short token: his own town")
with open(c.WORLD_CONFIG, "w") as f:
    json.dump({"enabled": True, "url": URL, "token": "y" * 32}, f)
check(isinstance(c.make_town(), c.WorldTown), "enabled with a url and token: the shared town")
os.remove(c.WORLD_CONFIG)

c.TOWN = c.WorldTown(URL, TEST_ROSTER["bolt"]["token"])     # the test roster's short token
c.TOWN.wc.timeout, c.TOWN.wc.retry = 1.0, (0, 0)
s = c.load_state()
s["tick"] = 50
c.save_state(s)
c.TOWN.wc.start_polling(s.setdefault("world", {}), every=0.05)

print("2. moving")
spike_go("lake")
turn("go", "lake")
check(s["location"] == "lake" and spike_sees().get("bolt", {}).get("state") == "awake", "he flies to the lake and Spike sees him there")
check(spike_sees()["bolt"].get("doing") is None, "a move clears what he was doing")
turn("fish")
check(spike_sees()["bolt"].get("doing") == "fishing", "Spike sees him fishing (the catch stays Bolt's)")
check("Spike" in next((p for p in PROMPTS[::-1] if '"action"' in p), ""), "his turn's prompt has the shared town in it")

print("3. talking with Spike at human speed")
spike.queue(sws, "say", text="Bolt! catch anything?", to="bolt")
spike.send(sws)
time.sleep(0.3)
check(c.has_talk(), "Spike's line wakes his quick reply")
s = c.run_step(c.reply_now, s)
c.send_outbox(s)
time.sleep(0.1)
back = [h for h in (spike.heard(sws) or []) if h["from"] == "bolt"]
check(back and back[-1]["text"] == "Kraa. Hey Spike." and back[-1]["to"] == "spike", "his answer reaches Spike, aimed at him")
check(any("**Spike:** Bolt! catch anything?" in p for p in POSTS), "and the conversation shows in his Discord diary")
check(not c.has_talk(), "nothing left waiting")

print("4. a crash mid-reply")
spike.queue(sws, "say", text="you still there?", to="bolt")
spike.send(sws)
time.sleep(0.3)
PLAN["broken"] = True
try:
    c.run_step(c.reply_now, s)
    check(False, "the broken reply raised")
except ConnectionError:
    pass
PLAN["broken"] = False
check(c.has_talk(), "the line he heard before crashing is still waiting")
s = c.run_step(c.reply_now, s)
c.send_outbox(s)
check(any("you still there?" in p for p in POSTS), "and he answers it")

print("5. Caelan's !leave, kept for Bolt")
c.inbox(c.PLACEMENTS, "creek|brass key|Caelan")
turn()
spike_go("creek")
items = (spike.look(sws, "creek", True) or {}).get("items", [])
check(any(i["name"] == "brass key" and i["for"] == "bolt" for i in items), "it's lying at the creek, reserved for Bolt")
spike.queue(sws, "take", item=items[0]["id"] if items else "x")
r = spike.send(sws)
check(r and not r[0][1]["ok"] and r[0][1]["reason"] == "reserved", "Spike can't take it")
turn("go", "creek")
turn()
check(hoard("brass key (left by Caelan at the creek)") == 1, "Bolt gets it when he gets there, as a gift from Caelan")
turn()
turn()
check(hoard("brass key") == 1 and not s.get("delivered"), "once, and it's acked")

print("6. a gift from Spike")
spike.queue(sws, "give", to="bolt", item="beetle")
spike.send(sws)
turn()
check(hoard("beetle (from Spike)") == 1 and c.is_gift("beetle (from Spike)"), "it lands in his hoard as a gift from Spike")

print("7. Spike's fir")
turn("go", "fir")
check(s["location"] == "fir" and spike_sees().get("bolt") is None, "he can fly to the fir in the shared town")
spike_go("fir")
check("bolt" in spike_sees(), "and Spike finds him at home")

print("8. the town goes away and comes back")
down()
t0 = time.time()
turn("go", "lake")
check(s["location"] == "lake" and time.time() - t0 < 5, "he lives on in his own town without stalling")
c.inbox(c.PLACEMENTS, "nest|red bead|Caelan")
turn()
check(any(e["body"]["action"] == "hide" for e in s.get("outbox", [])), "a !leave while it's away waits in his outbox")
check(not s["placed"].get("nest"), "(and isn't doubled into his own town)")
up()
turn()
spike_go("lake")
check(spike_sees().get("bolt", {}).get("state") == "awake", "when it's back, his own place wins: the lake")
check(not s.get("outbox"), "the !leave went through")
turn("go", "nest")
turn()
check(hoard("red bead (left by Caelan at the nest)") == 1, "and the red bead reaches him")

print("9. roosting")
spike_go("nest")
c.is_night = lambda: True
turn()
check(s.get("asleep_until") and spike_sees().get("bolt", {}).get("state") == "asleep", "he roosts, and Spike sees him asleep")
spike.queue(sws, "say", text="Bolt wake up", to="bolt")
r = spike.send(sws)
check(r and not r[0][1]["ok"] and r[0][1]["reason"] == "asleep", "the town won't let Spike talk to a sleeping crow")
c.is_night = lambda: False
s["asleep_until"] = 1
turn()
check(spike_sees().get("bolt", {}).get("state") == "awake", "morning: awake again")

down()
c.TOWN.wc.stop()
os.chdir("/")
shutil.rmtree(WORK, ignore_errors=True)
print(f"\nPROBLEMS: {len(PROBLEMS)}")
sys.exit(1 if PROBLEMS else 0)
