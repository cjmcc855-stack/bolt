#!/usr/bin/env python3
"""
reply_test.py - checks Bolt's quick replies: he answers right away, his turn knows what he said, humans can
wake him and creatures can't, and if the quick reply fails his turn still answers.

    python tests/reply_test.py [path/to/bolt_folder]

Runs on a fake brain in a temp folder. Nothing touches the real Bolt. Ends with PROBLEMS: 0.
"""
import importlib.util, json, os, shutil, sys, tempfile

SRC = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = SRC if os.path.isdir(SRC) else os.path.dirname(SRC)
WORK = tempfile.mkdtemp(prefix="bolt_reply_")
for f in os.listdir(SRC_DIR):
    if f.endswith(".py"):
        shutil.copy(os.path.join(SRC_DIR, f), os.path.join(WORK, f))
os.chdir(WORK)
spec = importlib.util.spec_from_file_location("creature", "creature.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
c.DISCORD = {}
c.real_weather = lambda: {"kind": "clear", "temp_f": 50, "wind_mph": 3, "real": False}
PROBLEMS, PROMPTS, POSTS = [], [], []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        PROBLEMS.append(what)


BROKEN = {"reply": False}


def brain(prompt, json_mode=True, temp=0.9, **kw):
    PROMPTS.append(prompt)
    if "just said this to you" in prompt or "Just said to you" in prompt:
        if BROKEN["reply"]:
            raise ConnectionError("brain hiccup (test)")
        return "Kraa, the river's loud tonight."
    if '"action"' in prompt:
        return json.dumps({"thought": "hm", "action": "think", "target": ""})
    if "List any NEW lasting facts" in prompt:
        return json.dumps({"facts": ["likes the river at night"]})
    if "How did it honestly make you feel" in prompt:
        return json.dumps({"feeling": 1, "reflection": "nice"})
    return "{}"


c.call_llm = brain
real_diary_post = c.discord_post
c.discord_post = lambda text, file=None: POSTS.append(text)

s = c.load_state()
s["tick"] = 50                                    # past the first-day reflection
c.save_state(s)

print("1. a human talks: he answers first, then his turn knows what he said")
c.inbox(c.TALK, "Caelan|how's the river tonight?")
s = c.run_step(c.reply_now, s)
check(any("**Bolt:** Kraa, the river's loud tonight." in p for p in POSTS), "the reply is posted by the quick step")
check(not c.has_talk(), "the talk was used up")
check(s["convo"][-1]["reply"] == "Kraa, the river's loud tonight.", "the conversation is remembered")
n_posts = len(POSTS)
PROMPTS.clear()
s = c.run_tick(s)
decision = next((p for p in PROMPTS if '"action"' in p), "")
check('You answered: "Kraa, the river' in decision, "his turn's decision knows what he just said")
check(not any("just said this to you" in p for p in PROMPTS), "his turn doesn't answer a second time")
check(s["people"].get("Caelan") and "likes the river at night" in s["people"]["Caelan"],
      "he still learns about the person (in the turn, after the reply went out)")
check("just_talked" not in s and "to_learn" not in s, "the hand-off notes are cleared after the turn")
check(len([p for p in POSTS if "how's the river tonight" in p]) == 1, "the conversation is posted once, not twice")

print("2. a gift and a hello at the same time")
c.inbox(c.OFFERINGS, "a shiny spoon (from Caelan)")
c.inbox(c.TALK, "Caelan|got you something!")
PROMPTS.clear()
s = c.run_step(c.reply_now, s)
check(any("a shiny spoon" in p for p in PROMPTS if "just said" in p), "the reply can see the gift being handed over")
check(os.path.getsize(c.OFFERINGS) > 0, "but the gift is still waiting for his turn (not taken by the reply)")
s = c.run_tick(s)
check(any(k.startswith("a shiny spoon") for k in c.hoard()["items"]), "and his turn takes it")

print("3. asleep")
s["asleep_until"] = 10 ** 12
c.inbox(c.CREATURE_TALK, "Spike|Bolt! wake up")
s = c.run_step(c.reply_now, s)
check(s["asleep_until"] and not c.has_talk(), "a creature can't wake him (and its line is let go)")
c.inbox(c.TALK, "Caelan|psst")
s = c.run_step(c.reply_now, s)
check(not s["asleep_until"] and any("wakes up to a visitor" in p for p in POSTS), "a human can")

print("4. if the quick reply fails, his turn answers instead")
BROKEN["reply"] = True
c.inbox(c.TALK, "Caelan|you there?")
before = json.dumps(s, sort_keys=True)
try:
    c.run_step(c.reply_now, s)
    check(False, "the failing reply raised")
except ConnectionError:
    pass
check(json.dumps(s, sort_keys=True) == before and c.has_talk(), "a failed reply changes nothing and the talk waits")
BROKEN["reply"] = False
s = c.run_tick(s)
check(any("you there?" in p for p in POSTS) and not c.has_talk(), "the turn picks it up and answers")

os.chdir("/")
shutil.rmtree(WORK, ignore_errors=True)
print(f"\nPROBLEMS: {len(PROBLEMS)}")
sys.exit(1 if PROBLEMS else 0)
