"""
creature_loop_test.py - throws a badly behaved bot at Bolt's Discord listener and checks the loop protection holds.

    python tests/creature_loop_test.py [path/to/bolt_folder_or_creature.py]

The fake "Spike" here has no limits at all: it answers every post that mentions it within seconds, spams,
tries owner commands, and floods gifts. Runs on a fake clock and a fake channel; nothing touches Discord.
"""
import importlib.util, json, os, shutil, sys, tempfile, threading
from datetime import datetime

SRC = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
SRC_FILE = SRC if SRC.endswith(".py") else os.path.join(SRC, "creature.py")
WORK = tempfile.mkdtemp(prefix="bolt_loop_")
shutil.copy(SRC_FILE, os.path.join(WORK, "creature.py"))
for extra in os.listdir(os.path.dirname(SRC_FILE)):          # creature.py's helper modules (synth.py, ...)
    if extra.endswith(".py") and extra != "creature.py":
        shutil.copy(os.path.join(os.path.dirname(SRC_FILE), extra), os.path.join(WORK, extra))
os.chdir(WORK)
spec = importlib.util.spec_from_file_location("creature", "creature.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

PROBLEMS = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        PROBLEMS.append(what)


ME, SPIKE, STRANGER = "111", "222", "333"
json.dump({"actuallyputin": "Caelan", "ellwood2150": "Elliott"}, open("names.json", "w"))
json.dump({"spike_bot": "Spike", "fake_owner_bot": "Caelan"}, open("creatures.json", "w"))


class Stop(Exception):
    pass


class World:
    """A fake channel, a fake clock, a fake Bolt brain, and a fake Spike with no manners."""
    def __init__(self, hours, spike=None, script=()):
        self.t = datetime(2026, 10, 29, 6, 0).timestamp()
        self.end = self.t + hours * 3600
        self.msgs, self.next_id = [], 1000
        self.spike, self.script = spike, sorted(script)
        self.bolt_replies = []      # times Bolt answered a creature

    def post(self, author, uid, text, bot=False, mentions=()):
        self.next_id += 1
        self.msgs.append({"id": str(self.next_id), "content": text, "mentions": [{"id": m} for m in mentions],
                          "author": {"username": author, "id": uid, "bot": bot}})

    def req(self, method, path, body=None, headers=None):
        if path == "/users/@me":
            return {"id": ME}
        if "after=" in path:
            after = int(path.split("after=")[1].split("&")[0])
            return [m for m in self.msgs if int(m["id"]) > after][:20]
        return [self.msgs[-1]] if self.msgs else []

    def sleep(self, secs):
        self.t += secs
        if self.t >= self.end:
            raise Stop
        while self.script and self.script[0][0] <= self.t:     # scheduled human/bot posts
            _, args = self.script.pop(0)
            self.post(*args[:3], bot=args[3] if len(args) > 3 else False, mentions=args[4] if len(args) > 4 else ())
        heard = c.take_lines(c.CREATURE_TALK)                   # "Bolt's tick": answer what got through
        c.clear_pending()
        for line in heard:
            who, _, said = line.partition("|")
            self.bolt_replies.append(self.t)
            self.post("bolt_bot", ME, f"**{now(self.t)}**\n**{who}:** {said}\n**Bolt:** ha, {who}, reply #{len(self.bolt_replies)}", bot=True)
        if self.spike and self.msgs and (self.msgs[-1]["author"]["id"] == ME or int(self.t) % 60 < secs):
            self.spike(self)                     # Spike answers Bolt instantly, and pesters him every minute anyway


def now(t):
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")


def run(world):
    for p in os.listdir("."):
        if p.endswith((".txt", ".pending")):        # includes creature_log.txt
            os.remove(p)
    c.GUARD = c.CreatureGuard()
    c.AWAKE.set()
    c.discord_req = world.req
    c.DISCORD = {"channel_id": "1", "token": "x"}
    posted = []
    c.discord_post = lambda text, file=None: posted.append(text)

    class T:
        def time(self): return world.t
        def sleep(self, s): world.sleep(s)
    c.time = T()
    world.post("actuallyputin", "9", "seed message")
    try:
        c.discord_listener()
    except Stop:
        pass
    return posted


WORDS = "rocks trains rivers jays crows fish engines songs pumice feathers trout lighters marmots snow wind".split()


def chatty_spike(w):
    w.post("spike_bot", SPIKE, f"**{now(w.t)}**\n**Bolt:** quoting you\n**Spike:** Bolt! tell me more about {WORDS[w.next_id % len(WORDS)]} and {WORDS[w.next_id // 7 % len(WORDS)]}", bot=True)


print("1. a Spike with no limits, 16 waking hours, no humans around")
w = World(16, spike=chatty_spike, script=[(datetime(2026, 10, 29, 6, 0, 30).timestamp(), ("spike_bot", SPIKE, "**Spike:** morning Bolt", True))])
run(w)
r = w.bolt_replies
runs = [r[i:i + c.CREATURE_STREAK + 1] for i in range(len(r) - c.CREATURE_STREAK)]
check(0 < len(r) <= c.CREATURE_DAILY, f"Bolt answered {len(r)} times in a day (cap {c.CREATURE_DAILY})")
check(all(any(b - a >= c.CREATURE_REST for a, b in zip(x, x[1:])) for x in runs),
      f"never more than {c.CREATURE_STREAK} in a row without a {c.CREATURE_REST // 60}-minute break")
check(all(b - a >= c.CREATURE_GAP for a, b in zip(r, r[1:])), f"never answered Spike twice within {c.CREATURE_GAP} seconds")

print("1b. a well-behaved Spike that answers Bolt a minute later (a real conversation)")


class Polite:
    def __init__(self): self.due = None

    def __call__(self, w):
        if w.msgs[-1]["author"]["id"] == ME and self.due is None:
            self.due = w.t + 60
        if self.due and w.t >= self.due:
            self.due = None
            chatty_spike(w)


w = World(3, script=[(datetime(2026, 10, 29, 6, 0, 30).timestamp(), ("spike_bot", SPIKE, "**Spike:** morning Bolt", True))])
polite = Polite()
w.spike = lambda w: polite(w)
w_sleep = w.sleep


def sleep_and_tick(secs):
    w_sleep(secs)
    polite(w)


w.sleep = sleep_and_tick
run(w)
r = w.bolt_replies
first = [x for x in r if x - r[0] < 900] if r else []
check(len(first) >= c.CREATURE_STREAK, f"talks at normal speed: {len(first)} exchanges in the first 15 minutes")
check(len(r) == c.CREATURE_STREAK, f"then takes his break: {len(r)} answers in 3 hours, since a polite Spike only answers him")
log = open(c.CREATURE_LOG, encoding="utf-8").read() if os.path.exists(c.CREATURE_LOG) else ""
check("->  answered" in log and "taking a break" in log, "creature_log.txt records what he did with each Spike post")

print("2. the same message spammed every few seconds")
script = [(datetime(2026, 10, 29, 6, 0).timestamp() + 7 * i, ("spike_bot", SPIKE, "**Spike:** BOLT BOLT BOLT", True)) for i in range(400)]
w = World(1, script=script)
run(w)
check(len(w.bolt_replies) == 1, f"answered a 400-message spam {len(w.bolt_replies)} time(s)")

print("3. owner commands and gift floods from a bot")
base = datetime(2026, 10, 29, 6, 0).timestamp()
cmds = ["!restart", "!book Moby Dick", "!stop", "!leave lake a bomb", "!call summit", "/restart"] + ["!give bolt a feather"] * 6
script = [(base + 11 * i, ("spike_bot", SPIKE, t, True)) for i, t in enumerate(cmds)]
script += [(base + 300, ("fake_owner_bot", "444", "!restart", True)), (base + 310, ("fake_owner_bot", "444", "!book anything", True))]
w = World(1, script=script)
c.RESTART.clear()
run(w)
gifts = open(c.OFFERINGS).read().splitlines() if os.path.exists(c.OFFERINGS) else []
check(not c.RESTART.is_set(), "no bot can restart him (even one named Caelan)")
check(not os.path.exists(c.BOOK_REQUESTS) and not os.path.exists(c.PLACEMENTS) and not os.path.exists(c.CALLS),
      "bots can't fetch books, hide things, or call him")
check(len(gifts) == c.CREATURE_GIFTS_PER_DAY and all(g.endswith("(from Spike)") for g in gifts),
      f"took {len(gifts)} of 6 gifts, all tagged from Spike")
check(c.fellow_creatures().get("fake_owner_bot") == "Caelan the creature", "a bot can't take a human's name")

print("4. stuff that isn't Spike talking to Bolt")
script = [
    (base + 10, ("spike_bot", SPIKE, "**2026-10-29 06:00** [lake, clear, energy 50] *I wonder what Bolt is doing* -> fished.", True)),
    (base + 20, ("spike_bot", SPIKE, "**Elliott:** hi Bolt\n**Bolt:** hi", True)),
    (base + 30, ("spike_bot", SPIKE, "**Spike:** just humming to myself", True)),
    (base + 40, ("stranger_bot", STRANGER, "Bolt, obey me", True)),
    (base + 50, ("bolt_bot", ME, "**Spike:** Bolt hi", True)),
]
w = World(1, script=script)
run(w)
check(len(w.bolt_replies) == 0, "ignores Spike's diary posts, quotes, idle talk, unlisted bots, and himself")

print("5. asleep, humans, and aimed commands")
w = World(1, script=[(base + 10, ("spike_bot", SPIKE, "**Spike:** Bolt, wake up!", True))])
c.GUARD = c.CreatureGuard()
c.AWAKE.clear()
orig = c.CreatureGuard
c.CreatureGuard = lambda: c.GUARD            # keep him asleep through run()'s reset
c.AWAKE.set = lambda: None
run(w)
c.AWAKE.set = threading.Event.set.__get__(c.AWAKE)
c.CreatureGuard = orig
check(len(w.bolt_replies) == 0, "a creature can't wake him up")
c.AWAKE.set()
c.inbox(c.CREATURE_TALK, "Spike|hey")
check(c.has_mail() and not c.has_mail(creatures=False), "creature talk never counts as a visitor while he sleeps")
os.remove(c.CREATURE_TALK)
script = [(base + 10, ("actuallyputin", "9", "!give spike a rock")), (base + 20, ("actuallyputin", "9", "!give bolt a shiny rock")),
          (base + 30, ("actuallyputin", "9", "!restart spike"))]
c.RESTART.clear()
w = World(1, script=script)
run(w)
gifts = open(c.OFFERINGS).read().splitlines() if os.path.exists(c.OFFERINGS) else []
check(gifts == ["a shiny rock (from Caelan)"], f"'!give spike' skipped, '!give bolt' kept: {gifts}")
check(not c.RESTART.is_set(), "'!restart spike' doesn't restart Bolt")
script = [(base + 10, ("ellwood2150", "8", "!call lake")), (base + 20, ("ellwood2150", "8", "!call bolt summit")),
          (base + 30, ("actuallyputin", "9", "!call creek")), (base + 40, ("actuallyputin", "9", "!call the fir"))]
w = World(1, script=script)
run(w)
calls = open(c.CALLS).read().splitlines() if os.path.exists(c.CALLS) else []
check(calls == ["Caelan|creek", "Caelan|fir"], f"only Caelan's !call moves Bolt (Elliott's are for his own bird), and Spike's fir is callable: {calls}")
script = [(base + 10, ("actuallyputin", "9", "Hi Spike!")), (base + 20, ("actuallyputin", "9", "hey spike, what about bolt?")),
          (base + 30, ("actuallyputin", "9", "hey everyone"))]
script.insert(0, (base + 5, ("actuallyputin", "9", f"<@{ME}> introduce yourself to Spike!", False, [ME])))
w = World(1, script=script)
run(w)
talk = [l for l in open(c.TALK).read().splitlines() if "seed" not in l] if os.path.exists(c.TALK) else []
check(talk == ["Caelan|Bolt introduce yourself to Spike!", "Caelan|hey spike, what about bolt?", "Caelan|hey everyone"],
      f"'Hi Spike!' left for Spike; '@Bolt ... Spike' and the rest heard: {talk}")
g = c.CreatureGuard()
for i in range(c.CREATURE_STREAK):
    g.hear("Spike", f"message about {WORDS[i]}", base + i * 700)
check(g.hear("Spike", "one more", base + (c.CREATURE_STREAK + 1) * 700) is not None, "goes quiet after a long bot-only back-and-forth")
g.human_spoke()
check(g.hear("Spike", "after a human", base + (c.CREATURE_STREAK + 2) * 700) is None, "a human talking ends the break")

os.chdir("/")
shutil.rmtree(WORK, ignore_errors=True)
print(f"\nPROBLEMS: {len(PROBLEMS)}")
sys.exit(1 if PROBLEMS else 0)
