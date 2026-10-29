#!/usr/bin/env python3
"""
habits_test.py - checks three of Bolt's habits:

  - flowery postcard replies get one plain rewrite in his own voice (plain ones are left alone)
  - ruts: getting fed up with something sinks in every time, and he's told plainly when a streak feels bad
  - roosting: at night he flies home and sleeps, with no model calls, until a human wakes him
  - songs: only the newest are kept as audio; older ones play back byte-identical from their recipes,
    and his early songs (no recipe) are never touched

    python tests/habits_test.py [path/to/bolt_folder]

Runs on a fake brain in a temp folder. Nothing touches the real Bolt. Ends with PROBLEMS: 0.
"""
import importlib.util, json, os, re, shutil, sys, tempfile

SRC = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = SRC if os.path.isdir(SRC) else os.path.dirname(SRC)
WORK = tempfile.mkdtemp(prefix="bolt_habits_")
for f in os.listdir(SRC_DIR):
    if f.endswith(".py"):
        shutil.copy(os.path.join(SRC_DIR, f), os.path.join(WORK, f))
os.chdir(WORK)
sys.path.insert(0, WORK)                         # so his synth.py loads, like it does next to creature.py
spec = importlib.util.spec_from_file_location("creature", "creature.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
c.DISCORD = {}
c.real_weather = lambda: {"kind": "clear", "temp_f": 50, "wind_mph": 3, "real": False}
c.is_night = lambda: False                          # daytime, except section 3
POSTS, PROMPTS = [], []
c.discord_post = lambda text, file=None: POSTS.append(text)
PROBLEMS = []
FLOWERY = ("The creek under the moonlight is a serene and magical place. The water sparkles like a silver ribbon, "
           "and the shadows dance around it. It's a perfect spot to let your mind wander.")
SAY = {"reply": FLOWERY, "rewrite": "Kraa. Cold, loud, moon on the water. You out there?", "broken": False}
TUNE = {"n": 0}


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        PROBLEMS.append(what)


def brain(prompt, json_mode=True, temp=0.9, **kw):
    PROMPTS.append(prompt)
    if "it came out long and fancy" in prompt:
        if SAY["broken"]:
            raise ConnectionError("brain hiccup (test)")
        return SAY["rewrite"]
    if "just said this to you" in prompt or "Just said to you" in prompt:
        return SAY["reply"]
    if "little synth tune" in prompt:
        TUNE["n"] += 1
        return json.dumps({"title": f"tune {TUNE['n']}", "scale": "A minor", "bpm": 100 + TUNE["n"],
                           "notes": [f"{'CDEFGAB'[(TUNE['n'] + i) % 7]}4:0.5" for i in range(8)]})
    if '"action"' in prompt:
        return json.dumps({"thought": "hm", "action": "think", "target": ""})
    if "How did it honestly make you feel" in prompt:
        return json.dumps({"feeling": 0, "reflection": "fine"})
    return "{}"


c.call_llm = brain
s = c.load_state()
s["tick"] = 50
c.save_state(s)

print("1. flowery replies")
check(c.too_purple(FLOWERY), "tonight's moonlight reply counts as flowery")
for plain in ("Kraa. Cold and loud, trout jumping. You fish it yet?", "Got a tangle of line again. Third time. Ugh.",
              "Hey Caelan! What's the surprise? Something shiny and new, I hope?"):
    check(not c.too_purple(plain), f"plain talk is left alone: {plain[:30]}...")
PROMPTS.clear()
c.inbox(c.TALK, "Caelan|how's the creek look under the moon?")
s = c.run_step(c.reply_now, s)
check(any(SAY["rewrite"] in p for p in POSTS) and not any("serene" in p for p in POSTS), "he says it again plainly")
check(sum("it came out long and fancy" in p for p in PROMPTS) == 1, "with exactly one extra try")
check(s["convo"][-1]["reply"] == SAY["rewrite"], "and the plain one is what he remembers saying")
PROMPTS.clear()
SAY["reply"] = "Kraa. Cold and loud tonight."
c.inbox(c.TALK, "Caelan|and now?")
s = c.run_step(c.reply_now, s)
check(not any("it came out long and fancy" in p for p in PROMPTS), "a plain reply costs no extra model call")
SAY["broken"] = True
out = c.plainer(s, FLOWERY)
check(out == "".join(re.findall(r"[^.!?]+[.!?]+", FLOWERY)[:3]).strip(), "if the rewrite fails he still answers")
check(out and len(out) <= len(FLOWERY), "(keeping at most his first three sentences)")
SAY.update(broken=False, rewrite='{"thought": "junk"}')
check(c.plainer(s, FLOWERY) != SAY["rewrite"], "junk from the model is never posted")

print("2. ruts")
s["recent_actions"] = ["fish"] * 4
s["recent_feelings"] = [-1, -1, -1, -1]
note = c.rut_note(s)
check("fish 4 turns in a row" in note and "worse" in note, "a bad streak is named plainly")
s["recent_feelings"] = [1, 0, 1, 1]
check(c.rut_note(s) == "", "a streak he's enjoying isn't")
s["recent_actions"] = ["fish", "fish"]
s["recent_feelings"] = [-1, -1]
check(c.rut_note(s) == "", "two in a row isn't a rut yet")
s["recent_actions"], s["recent_feelings"] = ["fish"] * 4, [-1] * 4
PROMPTS.clear()
s = c.run_tick(s)
decision = next((p for p in PROMPTS if '"action"' in p), "")
check("turns in a row now" in decision, "and it shows up in his turn")
check(s["recent_feelings"][-1] == 0 and len(s["recent_feelings"]) == 5, "each turn's feeling is kept next to its action")
src = open("creature.py", encoding="utf-8").read()
check("weight = novelty if feeling > 0 else 1" in src, "bad feelings aren't watered down by repetition")

print("3. roosting")
c.is_night = lambda: True
s["location"], s["energy"], s["asleep_until"] = "creek", 60, 0
s.pop("human_at", None)
PROMPTS.clear()
s = c.run_tick(s)
check(not PROMPTS, "at night his turn makes no model calls")
check(s["location"] == "nest" and s["asleep_until"] > c.time.time() + 3000, "he flies home and goes to sleep")
check("roosted" in s["memories"][-1]["text"] or "tucked into the nest" in s["memories"][-1]["text"], "and remembers going to bed")
for _ in range(5):
    s = c.run_tick(s)
check(not PROMPTS and s["asleep_until"], "he sleeps through the night without thinking")
c.inbox(c.CREATURE_TALK, "Spike|Bolt! you up?")
s = c.run_step(c.reply_now, s)
check(s["asleep_until"] and not PROMPTS, "another creature can't wake him")
SAY["reply"] = "Kraa. Up now. What's up?"
c.inbox(c.TALK, "Caelan|you awake?")
s = c.run_step(c.reply_now, s)
check(not s["asleep_until"] and any("Up now" in p for p in POSTS), "a human can, and he answers")
PROMPTS.clear()
s = c.run_tick(s)
check(any('"action"' in p for p in PROMPTS) and not s["asleep_until"], "and he stays up while they're around")
s["human_at"] -= c.ROOST_AFTER_VISIT + 1
PROMPTS.clear()
s = c.run_tick(s)
check(not PROMPTS and s["asleep_until"], "20 minutes after they go quiet, he roosts again")
s["location"], s["energy"], s["asleep_until"] = "summit", 8, 0
s.pop("human_at", None)
s = c.run_tick(s)
check(s["location"] == "summit" and s["asleep_until"], "too worn out to fly home: he sleeps where he is")
c.is_night = lambda: False
s["asleep_until"] = 1
PROMPTS.clear()
s = c.run_tick(s)
check(any('"action"' in p for p in PROMPTS), "morning: he wakes and lives his day")

print("4. songs")
os.makedirs("songs", exist_ok=True)
with open("songs/00001_an_early_song.wav", "wb") as f:      # one of his first songs: audio only, no recipe
    f.write(b"RIFF....early")
made = {}
for i in range(45):
    s["tick"] = 100 + i
    out = c.do_music("the creek", s)
    name = os.path.basename(s.pop("_file"))
    with open(f"songs/{name}", "rb") as f:
        made[name] = f.read()
c.prune_songs()
wavs = sorted(f for f in os.listdir("songs") if f.endswith(".wav"))
check(len(wavs) == c.KEEP_AUDIO + 1, f"newest {c.KEEP_AUDIO} kept as audio (plus the early one)")
check("00001_an_early_song.wav" in wavs, "his early song without a recipe is never touched")
gone = [n for n in made if n not in wavs]
check(len(gone) == 5, "the 5 oldest new songs went back to just their recipe")
check(all(c.render_song(n) == made[n] for n in gone), "and they play back byte-identical")
check(set(made) | {"00001_an_early_song.wav"} <= set(c.song_names()), "every song is still listed")
check(c.render_song("00001_an_early_song.wav") is None, "a song with no recipe is only ever the file")
if c.synth is not None:
    os.makedirs("patches", exist_ok=True)
    secs, played = c.synth.render({"title": "test patch", "bpm": 110}, "songs/00099_test_patch.wav", level=3)
    played["song"] = "00099_test_patch.wav"
    with open("patches/00099_test_patch.json", "w", encoding="utf-8") as f:
        json.dump(played, f)
    with open("songs/00099_test_patch.wav", "rb") as f:
        orig = f.read()
    os.remove("songs/00099_test_patch.wav")
    check(c.render_song("00099_test_patch.wav") == orig, "a synth song plays back byte-identical from its patch")

os.chdir("/")
shutil.rmtree(WORK, ignore_errors=True)
print(f"\nPROBLEMS: {len(PROBLEMS)}")
sys.exit(1 if PROBLEMS else 0)
