"""
sim_days.py - runs Bolt through days of life in fast-forward with a chaotic fake brain,
and checks after every tick that nothing important broke.

    python tests/sim_days.py [path/to/bolt_folder_or_creature.py] [--ticks 900] [--seed 1]

Nothing touches the real Bolt: everything runs in a temporary copy.
"""
import argparse, collections, datetime as _dt, importlib.util, io, json, os, random, shutil, sys, tempfile, time as _time

ap = argparse.ArgumentParser()
ap.add_argument("src", nargs="?", default=os.path.join(os.path.dirname(__file__), ".."))
ap.add_argument("--ticks", type=int, default=900)
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--state", default=None, help="optional real state.json to start from")
ap.add_argument("--keep", action="store_true", help="keep the temporary sim folder for inspection")
args = ap.parse_args()
random.seed(args.seed)

SRC = os.path.abspath(args.src)
SRC_DIR = SRC if os.path.isdir(SRC) else os.path.dirname(SRC)
WORK = tempfile.mkdtemp(prefix="bolt_sim_")
for name in os.listdir(SRC_DIR):
    p = os.path.join(SRC_DIR, name)
    if name.endswith(".py") or name == "bolt" or name == "world.html":
        (shutil.copytree if os.path.isdir(p) else shutil.copy)(p, os.path.join(WORK, name))
os.makedirs(os.path.join(WORK, "library"), exist_ok=True)
with open(os.path.join(WORK, "library", "Test_Book_of_Rocks.txt"), "w") as f:
    f.write("*** START OF THE PROJECT GUTENBERG EBOOK ***\n" + ("Agate glows when you hold it to the light. " * 40 + "\n\n") * 30)
if args.state:
    shutil.copy(args.state, os.path.join(WORK, "state.json"))
os.chdir(WORK)
sys.path.insert(0, WORK)

# ---------------- simulated clock: 5 minutes per tick, starting 9pm so nights get tested ----------------
CLOCK = [_dt.datetime(2026, 10, 28, 21, 0).timestamp()]


class FakeDT(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls.fromtimestamp(CLOCK[0])


class FakeTime:
    def time(self): return CLOCK[0]
    def sleep(self, s): CLOCK[0] += min(s, 1)
    def __getattr__(self, k): return getattr(_time, k)


spec = importlib.util.spec_from_file_location("creature", os.path.join(WORK, "creature.py"))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
mods = [c] + [m for n, m in sys.modules.items() if n.startswith("bolt.")]
for m in mods:
    if hasattr(m, "datetime"): m.datetime = FakeDT
    if hasattr(m, "time"): m.time = FakeTime()
    if hasattr(m, "DISCORD"): m.DISCORD = {}

# ---------------- fake internet ----------------
class R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


NET = {"down": False}


def fake_urlopen(req, timeout=0):
    url = req.full_url if hasattr(req, "full_url") else str(req)
    if NET["down"] or random.random() < 0.1:
        raise OSError("network down (simulated)")
    if "open-meteo" in url:
        return R(json.dumps({"current": {"temperature_2m": random.uniform(10, 80), "wind_speed_10m": random.uniform(0, 35),
                                         "weather_code": random.choice([0, 1, 2, 3, 45, 51, 61, 63, 71, 75, 95])}}).encode())
    if "w/api.php" in url:
        return R(json.dumps({"query": {"search": [{"title": "Yellow-bellied marmot"}]}}).encode())
    if "rest_v1/page/summary" in url:
        return R(json.dumps({"extract": "The yellow-bellied marmot whistles to warn its colony."}).encode())
    if "gutenberg.org/ebooks/search" in url:
        return R(b'<a href="/ebooks/42">x</a>')
    if "gutenberg.org/cache" in url:
        return R(("Title: A Fake Book\nAuthor: Nobody\n*** START OF THE PROJECT GUTENBERG EBOOK ***\n" + "words " * 2000).encode())
    raise OSError(f"unexpected url in test: {url}")


for m in mods:
    if hasattr(m, "urllib"): m.urllib.request.urlopen = fake_urlopen

# ---------------- chaotic brain ----------------
PROMPT_SIZES = []
STATS = collections.Counter()


def junk():
    return random.choice(["", "lol", "{not json", "[1,2,3]", '"just a string"', "null", "{}", '{"action": 7}', "x" * 5000])


def brain(prompt, json_mode=True, temp=0.9):
    prompt = c.fit_prompt(prompt)
    PROMPT_SIZES.append(len(c.PERSONA) + len(prompt))
    roll = random.random()
    if roll < 0.04:
        raise ConnectionError("ollama hiccup (simulated)")
    if roll < 0.12:
        STATS["junk replies"] += 1
        return junk()
    if '"thought"' in prompt and '"action"' in prompt:
        action = random.choice(c.ACTIONS + ["fly_to_moon", ""])
        target = random.choice(list(c.PLACES) + ["the summit", "river", "the old barn", "hidden meadow", "garnet", "jasper and quartz",
                                                  "railroad spike", "Test Book", "marmots", "", "Caelan's gift", "♥ weird ünïcode"])
        return json.dumps({"thought": random.choice(["hm", "the wind is loud", "x" * 400]), "action": action, "target": target,
                           "gift_reaction": random.choice(["", "KRAA mine!", ["a", "list"]])})
    if "A human just said" in prompt:
        return random.choice(["Hey. The river's loud today.", "Bolt: \"Kraa.\"", "", "x" * 3000])
    if "synth tune" in prompt:
        return json.dumps({"title": random.choice(["Wind", "Wind", "Fog", None, 5]), "scale": "A minor",
                           "bpm": random.choice([72, "fast", 9999, None]),
                           "notes": random.choice([["A3:1", "C4:0.5", "E#4:1", "rest:1", "Q9:x", "G4:2"], "C4:1 D4:1", None])})
    if "SVG picture" in prompt:
        return random.choice(['<svg><rect width="200" height="200" fill="#abc"/><script>x()</script></svg>', "no svg for you"])
    if "tinkering" in prompt:
        return json.dumps({"name": random.choice(["wind chime", "(made from) | trap", "x" * 200]), "what_it_does": "clinks"})
    if "What did you think?" in prompt:
        return json.dumps({"reaction": "neat", "words": random.choice([["glow"], "glow", None]),
                           "facts": random.choice([["agate glows in light"], "agate glows", None, [1, 2]]),
                           "topic": random.choice(list(c.TOPICS) + ["other", "nonsense"])})
    if "List any NEW facts" in prompt:
        return json.dumps({"facts": random.choice([["loves fishing"], "drives a white coupe", None, []])})
    if "paging back" in prompt:
        return json.dumps({"reflection": "I was so young.", "feeling": random.choice([2, "big", None])})
    if "How did it honestly make you feel" in prompt:
        return json.dumps({"feeling": random.choice([-2, -1, 0, 1, 2, 99, "happy", None]), "reflection": "ok"})
    return random.choice(["I love the mountain and shiny things.", "Short sentences. Kraa.", junk()])


for m in mods:
    if hasattr(m, "call_llm"): m.call_llm = brain

# ---------------- crash injection: sometimes the "power goes out" mid-save ----------------
real_atomic = c.atomic_save


def flaky_atomic(path, obj):
    if random.random() < 0.02:
        with open(path + ".tmp", "w") as f:
            f.write('{"half": ')                 # power cut halfway through writing
        STATS["crashes mid-save"] += 1
        raise OSError("power cut (simulated)")
    return real_atomic(path, obj)


for m in mods:
    if hasattr(m, "atomic_save"): m.atomic_save = flaky_atomic

# ---------------- run ----------------
problems = []
GIFTS_EVER = set()


def check(s, n):
    def bad(msg): problems.append(f"tick {n}: {msg}")
    if not 0 <= s["energy"] <= 100: bad(f"energy out of range: {s['energy']}")
    if not -5 <= s["mood"] <= 5: bad(f"mood out of range: {s['mood']}")
    if s["location"] not in c.PLACES: bad(f"invalid location {s['location']}")
    if len(s["collection"]) > c.SHELF_MAX: bad("shelf over max")
    if any(abs(v) > 3.0001 for v in s["prefs"].values()): bad("pref out of range")
    h = c.hoard()["items"]
    if any(v["count"] <= 0 for v in h.values()): bad("hoard item with count <= 0")
    dup = [k for k, v in h.items() if v["gift"] and v["count"] > 1 and "#" in k]
    if dup: bad(f"gift counted twice (retry duplicated it): {dup[:3]}")
    lost = [g for g in GIFTS_EVER if g not in h]
    if lost: bad(f"GIFTS LOST: {lost}")
    if any(len(v) > c.PEOPLE_MAX for v in s.get("people", {}).values()): bad("too many people facts")
    if len(str(s.get("likes", ""))) > 1000: bad("likes too long")
    try:
        with open(c.STATE_FILE) as f:
            json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        bad(f"state.json unreadable on disk: {e}")
    if os.path.exists(c.MEMORY_BOOK):
        with open(c.MEMORY_BOOK, encoding="utf-8") as f:
            for i, line in enumerate(f):
                try:
                    json.loads(line)
                except ValueError:
                    bad(f"memory book line {i} is broken"); break


s = c.load_state()
failures = 0
t0 = _time.time()
for n in range(1, args.ticks + 1):
    CLOCK[0] += 300
    NET["down"] = (n // 60) % 7 == 3                     # an internet outage every so often
    r = random.random()
    if r < 0.06:
        c.inbox(c.TALK, f"Caelan|{random.choice(['hey bolt', 'how was the river?', 'x' * 900, 'pipes | and | newlines'])}")
    elif r < 0.09:
        g = f"{random.choice(['a shiny spoon', 'a garnet', 'an old key'])} #{n} (from Caelan)"
        c.inbox(c.OFFERINGS, g); GIFTS_EVER.add(g)
    elif r < 0.11:
        place = random.choice(list(c.PLACES)); item = f"a lure #{n}"
        c.inbox(c.PLACEMENTS, f"{place}|{item}"); GIFTS_EVER.add(f"{item} (left by Caelan at the {place})")
    elif r < 0.12:
        c.inbox(c.CALLS, f"Caelan|{random.choice(list(c.PLACES))}")
    elif r < 0.125:
        c.inbox(c.BOOK_REQUESTS, "a fake book")
        c.process_book_requests()
    try:
        s = c.run_tick(s)
        failures = 0
        STATS["ticks ok"] += 1
        STATS[f"did: {s.get('last', {}).get('action', 'sleeping')}"] += 1
    except Exception as e:
        failures += 1
        STATS["ticks failed (retried later)"] += 1
        STATS[f"fail: {type(e).__name__}"] += 1
        # like the real Bolt: memory is reloaded from disk after a failure
        if random.random() < 0.3:
            c.HOARD = None
            s = c.load_state()
    # gifts only count as "given" once Bolt has actually received them; pending ones wait in the inbox
    pending_gifts = set()
    for fp in (c.OFFERINGS, c.OFFERINGS + ".pending"):
        if os.path.exists(fp):
            pending_gifts |= {l.strip() for l in open(fp, encoding="utf-8") if l.strip()}
    received = {g for g in GIFTS_EVER if g not in pending_gifts and "(left by" not in g}
    placed_waiting = {f"{i} (left by Caelan at the {p})" for p, items in s["placed"].items() for i in items}
    for fp in (c.PLACEMENTS, c.PLACEMENTS + ".pending"):
        if os.path.exists(fp):
            for l in open(fp, encoding="utf-8"):
                p, _, i = l.strip().partition("|")
                placed_waiting.add(f"{i} (left by Caelan at the {p})")
    left_found = {g for g in GIFTS_EVER if "(left by" in g and g not in placed_waiting}
    saved_gifts = GIFTS_EVER
    GIFTS_EVER = received | left_found
    if not failures:
        check(s, n)
    GIFTS_EVER = saved_gifts

# final: reload everything from disk the way a restart would
c.HOARD = None
s2 = c.load_state()
waiting = {f"{i} (left by Caelan at the {p})" for p, items in s2["placed"].items() for i in items}
for fp in (c.PLACEMENTS, c.PLACEMENTS + ".pending", c.OFFERINGS, c.OFFERINGS + ".pending"):
    if os.path.exists(fp):
        for l in open(fp, encoding="utf-8"):
            p, _, i = l.strip().partition("|")
            waiting |= {l.strip(), f"{i} (left by Caelan at the {p})"}
GIFTS_EVER = {g for g in GIFTS_EVER if g not in waiting}
check(s2, "after restart")
print(f"  gifts still waiting to be found/received: {len(waiting & saved_gifts)}")

# ---------------- world page smoke test ----------------
import threading, urllib.request as _u
try:
    srv = c.WorldServer(("127.0.0.1", 0), c.WorldHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    real_open = _u.build_opener().open
    st = json.loads(real_open(base + "/api/state", timeout=5).read())
    for key in ("location", "hoard", "memory_count", "places", "notebooks"):
        if key not in st: problems.append(f"world API missing {key}")
    for path, body in (("/api/talk", {"text": "hi"}), ("/api/give", {"item": "a spoon"}),
                       ("/api/place", {"place": "lake", "item": "a lure"}), ("/api/call", {"place": "summit"})):
        r = real_open(_u.Request(base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}), timeout=5)
        if json.loads(r.read()).get("ok") is not True: problems.append(f"world {path} failed")
    try:
        real_open(_u.Request(base + "/api/place", data=b'{"place":"mars","item":"x"}'), timeout=5)
        problems.append("world accepted a place that doesn't exist")
    except Exception:
        pass
    try:
        real_open(base + "/songs/..%2f..%2fstate.json", timeout=5)
        problems.append("world served a file outside songs/")
    except Exception:
        pass
    srv.shutdown()
    print("  world page: ok")
except Exception as e:
    problems.append(f"world page smoke test crashed: {e}")

print(f"\n=== {args.ticks} ticks (~{args.ticks * 5 / 60 / 24:.1f} days) in {(_time.time() - t0):.1f}s, sim dir {WORK}")
for k, v in sorted(STATS.items()):
    print(f"  {k}: {v}")
print(f"  largest prompt: {max(PROMPT_SIZES)} chars (budget {c.PROMPT_BUDGET})")
print(f"  skills: {s2.get('skills')}  | hoard kinds: {len(c.hoard()['items'])}  | memory book: {c.book_overview()[0]}")
print(f"  gifts given: {len(GIFTS_EVER)}  | gifts in hoard: {sum(1 for v in c.hoard()['items'].values() if v['gift'])}")
over = [p for p in PROMPT_SIZES if p > c.PROMPT_BUDGET + 200]
if over:
    problems.append(f"{len(over)} prompts over budget (max {max(over)})")
print(f"\nPROBLEMS: {len(problems)}")
for p in problems[:40]:
    print("  " + p)
os.chdir(os.path.dirname(WORK))
if not args.keep:
    shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if problems else 0)
