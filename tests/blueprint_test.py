#!/usr/bin/env python3
"""
blueprint_test.py - checks the blueprint puzzle: studying one of Caelan's blueprints works out its parts one at a
time, the junkyard only gives up parts he knows he's looking for, he can't build until he understands the drawing
and every part and has built what goes inside it, building never uses up the blueprint, and what he builds really
changes things (travel, naps, trains, skills). Reading about go-karts is enough to build one without a blueprint.

    python tests/blueprint_test.py [path/to/bolt_folder]

Runs on a fake brain in a temp folder. Nothing touches the real Bolt. Ends with PROBLEMS: 0.
"""
import importlib.util, json, os, random, shutil, sys, tempfile

SRC = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = SRC if os.path.isdir(SRC) else os.path.dirname(SRC)
WORK = tempfile.mkdtemp(prefix="bolt_blueprint_")
for f in os.listdir(SRC_DIR):
    if f.endswith(".py"):
        shutil.copy(os.path.join(SRC_DIR, f), os.path.join(WORK, f))
os.makedirs(os.path.join(WORK, "library"))
shutil.copy(os.path.join(SRC_DIR, "library", "The_Tinkerers_Handbook.txt"), os.path.join(WORK, "library"))
os.chdir(WORK)
sys.path.insert(0, WORK)
spec = importlib.util.spec_from_file_location("creature", "creature.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
c.DISCORD = {}
c.real_weather = lambda: {"kind": "clear", "temp_f": 50, "wind_mph": 3, "real": False}
c.is_night = lambda: False
c.discord_post = lambda text, file=None: None
PROBLEMS, PROMPTS = [], []
FACT = {"n": 0}


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        PROBLEMS.append(what)


def brain(prompt, json_mode=True, temp=0.9, **kw):
    PROMPTS.append(prompt)
    if "examining your" in prompt:
        FACT["n"] += 1
        return json.dumps({"new": True, "discovery": "huh", "fact": f"it has a part number stamped on it {FACT['n']}",
                           "topic": "other"})
    if "What did you think?" in prompt:
        return json.dumps({"reaction": "neat", "words": [], "facts": [], "topic": "other"})
    if '"action"' in prompt:
        return json.dumps({"thought": "hm", "action": "think", "target": ""})
    return "{}"


c.call_llm = brain
s = c.load_state()
s["tick"] = 50
random.seed(3)
V8 = "For Bolt: blueprint of a twin-turbo V8, exploded view (left by Caelan at the junkyard)"
CAM = "For Bolt: blueprint for cutting a camshaft by hand (left by Caelan at the machine_shop)"
BIG = "For Bolt: blueprint of a '69 Charger's 440 big block (left by Caelan at the garage)"
for bp in (V8, CAM, BIG):
    c.add_item(s, bp)

print("1. studying a blueprint works out one thing at a time")
check(c.blueprint_of(V8) == "v8" and c.blueprint_of(CAM) == "camshaft" and c.blueprint_of(BIG) == "bigblock",
      "each hidden blueprint is recognized")
check(c.blueprint_of("blueprint of a twin-turbo V8") is None, "a blueprint that isn't a gift doesn't count")
out = c.do_examine("blueprint twin-turbo V8", s)
check("calls for an engine block" in out, f"the first look finds the first part ({out[:80]})")
check(c.needed_parts(s) == ["engine block"], "now he knows what he's looking for")
check("twin-turbo V8 (1 of 4 things worked out" in c.blueprint_note(s), "his turn sees his progress")
for _ in range(3):
    out = c.do_examine("blueprint twin-turbo V8", s)
check("goes together" in out and s["blueprints"]["v8"]["learned"] == 4, "four looks and he understands it")
check("already understand it" in c.do_examine("blueprint twin-turbo V8", s), "a fifth look teaches nothing more")

print("2. the junkyard has the parts, but only the ones he knows to look for")
s["location"] = "junkyard"
found = []
for _ in range(60):
    out = c.execute("scavenge", "", s, "quiet")
    s["energy"] = 90
    if "parts you've been looking for" in out:
        found.append(out)
check(found and all(c.owns_part(p) for p in c.BLUEPRINTS["v8"][3]), "scavenging turned up every V8 part")
check(not c.owns_part("set of lifters"), "but not camshaft parts he hasn't worked out yet")
check(c.needed_parts(s) == [], "nothing left to look for")

print("3. building needs every piece of understanding")
s["location"] = "garage"
check("gets built at the junkyard" in c.do_build("the twin-turbo V8", s), "it has to be built in its place")
s["location"] = "junkyard"
out = c.do_build("the twin-turbo V8", s)
check("don't understand the engine block" in out, f"he has to understand each part first ({out[:90]})")
check(c.didnt_happen(out), "a build that didn't happen isn't a win")
for p in c.BLUEPRINTS["v8"][3]:
    c.do_examine(p, s)
s["skills"]["tinkering"] = 4 * 2 ** 2                  # level 2: not enough for a V8
out = c.do_build("the twin-turbo V8", s)
check("tinkering isn't up to it" in out, "and enough tinkering")
s["skills"]["tinkering"] = 4 * 3 ** 2
s["energy"] = 80
out = c.do_build("the twin-turbo V8", s)
check(out.startswith("built the twin-turbo V8") and c.working(s, "v8"), f"then it gets built ({out[:60]})")
check(not any(c.owns_part(p) for p in c.BLUEPRINTS["v8"][3]), "the parts went into it")
check(V8 in c.hoard()["items"], "the blueprint is a gift and is never used up")
check("already built it" in c.do_build("twin-turbo V8", s), "he can't build it twice")

print("4. big machines need smaller ones inside them")
for _ in range(len(c.blueprint_steps("bigblock"))):
    c.do_examine("blueprint 440 big block", s)
for p in c.BLUEPRINTS["bigblock"][3]:
    c.add_item(s, p)
    c.do_examine(p, s)
s["location"], s["skills"]["tinkering"] = "garage", 4 * 4 ** 2
out = c.do_build("440 big block", s)
check("needs a working hand-cut camshaft first" in out, f"no camshaft, no big block ({out[:90]})")
s["built"]["camshaft"] = {"when": "earlier"}
out = c.do_build("440 big block", s)
check(out.startswith("built the 440 big block") and s["built"]["camshaft"].get("in") == "bigblock",
      "with a camshaft it's built, and the camshaft goes inside it")
check(not c.working(s, "camshaft") and c.built(s, "camshaft"), "an installed camshaft isn't standing on its own")

print("5. no plans, no building")
s2 = c.load_state()
saved = dict(c.hoard()["items"])
c.hoard()["items"].clear()
check("don't have any blueprints or plans" in c.do_build("a go-kart", s2), "without a plan he can't build")
c.hoard()["items"].update(saved)
check("don't have a plan for that" in c.do_build("a spaceship", s), "nor something he has no plan for")

print("6. reading about go-karts is enough to build one")
s["books"] = {}
check("gokart" not in c.my_plans(s), "before reading, a go-kart isn't one of his plans")
reads = [c.do_read("tinkerer", s) for _ in range(8)]
check(sum("go-kart takes" in r for r in reads) == 1, "one passage of the Tinkerer's Handbook teaches him about go-karts")
check(s["blueprints"].get("gokart", {}).get("learned") == len(c.blueprint_steps("gokart")), "he knows what a go-kart takes")
check("gokart" in c.my_plans(s), "it's one of his plans now")
book = open("library/The_Tinkerers_Handbook.txt", encoding="utf-8").read()
check("junkyard" in book and "blueprint" in book.lower(), "the handbook points him to the junkyard for parts")
s["location"] = "junkyard"
for _ in range(80):
    c.execute("scavenge", "", s, "quiet")
    s["energy"] = 90
check(all(c.owns_part(p) for p in c.BLUEPRINTS["gokart"][3]), "the junkyard has every go-kart part")
for p in c.BLUEPRINTS["gokart"][3]:
    c.do_examine(p, s)
out = c.do_build("go kart", s)
check(out.startswith("built the go-kart from your own plan"), f"lil man builds a go-kart ({out[:60]})")

print("7. what he builds changes things")
s["energy"], s["location"] = 80, "junkyard"
out = c.execute("go", "creek", s, "quiet")
check(out == "drove the go-kart from junkyard to creek" and s["energy"] == 76, f"he drives the go-kart ({out})")
s["built"]["hotrod"] = {"when": "now"}
s["energy"] = 80
c.execute("go", "lake", s, "quiet")
check(s["energy"] == 78, "the hot rod is cheaper still")
s["energy"] = 80
out = c.execute("go", "mountain_trail", s, "quiet")
check(out.startswith("flew") and s["energy"] == 68, "no driving up the mountain")
s["built"]["cablecar"] = {"when": "now"}
s["energy"] = 30
out = c.execute("go", "summit", s, "quiet")
check(out.startswith("rode the cable car") and s["location"] == "summit", "the cable car takes him up even tired")
s["built"]["telescope"] = {"when": "now"}
check(any(c.execute("watch", "", s, "a cloud")[len("sat and watched: "):] in c.SKY_EVENTS for _ in range(20)),
      "the radio telescope listens to the sky")
s["location"], s["energy"] = "diner_roof", 10
c.execute("nap", "", s, "quiet")
check(s["energy"] == 45, "a plain nap on the diner roof")
s["built"]["turbine"], s["energy"] = {"when": "now"}, 10
c.execute("nap", "", s, "quiet")
check(s["energy"] == 60, "with the turbine the vent is warm")
s["location"] = "rail_yard"
s["built"]["valve"] = {"when": "now"}
trains = []
for _ in range(10):
    c.add_item(s, "bottle cap")
    trains.append("roared over it" in c.do_activity("penny_on_tracks", "bottle cap", s))
    s["energy"] = 80
check(all(trains), "with the valve gear a train always comes")
before = c.know_levels(s, "tinker")
s["built"]["welder"] = {"when": "now"}
check(c.know_levels(s, "tinker") == before + 2, "the welder makes his tinkering better")
note = c.blueprint_note(s)
check("Machines you've built:" in note and "go-kart" in note and "camshaft" not in note.split("built:")[1],
      "his turn knows what he's built (not what's inside something else)")
c.add_item(s, "length of steel tubing")
c.add_item(s, "cracked bottle cap")
c.add_item(s, "bent key")
s["location"] = "shed"
c.do_activity("tinker", "", s)
check(c.owns_part("length of steel tubing"), "random tinkering never grabs a machine part")

print("8. his turn sees the build action")
PROMPTS.clear()
s = c.run_tick(s)
decision = next((p for p in PROMPTS if '"action"' in p), "")
check("build (target = a machine you have plans for)" in decision and "Machines you've built:" in decision,
      "the decision prompt offers build and lists his machines")

os.chdir("/")
shutil.rmtree(WORK, ignore_errors=True)
print(f"\nPROBLEMS: {len(PROBLEMS)}")
sys.exit(1 if PROBLEMS else 0)
