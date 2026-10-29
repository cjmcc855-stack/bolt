#!/usr/bin/env python3
"""
town_test.py - checks the plumbing Bolt needs for the shared town (shasta-world), using a fake town:

  - he can wake up somewhere his own town doesn't have (Spike's fir) and still live a normal turn
  - save first, then send: what a step queues for the town is on disk before it's sent
  - a give/drop/take with no answer is resent with the same id; other actions are let go
  - after a restart only give/drop/take are resent; a failed turn sends nothing
  - a retried turn uses new ids
  - he notices who's with him (diary + memory), his replies know it, and he's told when a creature parrots him
  - "your friend" / "the jay" / "Elliott's guy" bring up who Spike is and what they last said to each other
  - names are never banned as crutch words
  - he can start a conversation with an awake creature here (talk_to -> a town 'say'); 'go Spike' is answered
    plainly; something that didn't happen can't feel like a win; stray Chinese leaves song titles

    python tests/town_test.py [path/to/bolt_folder]

Runs on a fake brain in a temp folder. Nothing touches the real Bolt. Ends with PROBLEMS: 0.
"""
import importlib.util, json, os, shutil, sys, tempfile, time

SRC = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = SRC if os.path.isdir(SRC) else os.path.dirname(SRC)
WORK = tempfile.mkdtemp(prefix="bolt_town_")
for f in os.listdir(SRC_DIR):
    if f.endswith(".py"):
        shutil.copy(os.path.join(SRC_DIR, f), os.path.join(WORK, f))
os.chdir(WORK)
spec = importlib.util.spec_from_file_location("creature", "creature.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
c.DISCORD = {}
c.real_weather = lambda: {"kind": "clear", "temp_f": 50, "wind_mph": 3, "real": False}
c.is_night = lambda: False                          # these checks are about daytime (roosting: habits_test)
c.discord_post = lambda text, file=None: None
PROBLEMS, PROMPTS = [], []
PLAN = {"action": "think", "target": "", "broken": False}


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        PROBLEMS.append(what)


def brain(prompt, json_mode=True, temp=0.9, **kw):
    PROMPTS.append(prompt)
    if "just said this to you" in prompt or "Just said to you" in prompt:
        return "Kraa."
    if '"action"' in prompt:
        if PLAN["broken"]:
            raise ConnectionError("brain hiccup (test)")
        return json.dumps({"thought": "hm", "action": PLAN["action"], "target": PLAN["target"]})
    if "How did it honestly make you feel" in prompt:
        return json.dumps({"feeling": PLAN.get("feel", 0), "reflection": "fine"})
    if "You start talking to" in prompt:
        return "Found a beetle under the old tire. Want half?"
    return "{}"


c.call_llm = brain


class FakeTown(c.LocalTown):
    """Queues a 'doing' after every turn, a 'say' after every reply, and a 'give' when he thinks."""
    name = "the fake town"

    def __init__(self):
        self.sent, self.answer, self.applied, self.on_disk = [], {}, [], []

    def after_turn(self, s, action, target, outcome):
        c.queue_action(s, "doing", text=action)
        if action == "think":
            c.queue_action(s, "give", to="spike", item="bottle cap")

    def after_reply(self, s, heard, reply):
        c.queue_action(s, "say", text=reply)

    def send(self, body):
        with open(c.STATE_FILE, encoding="utf-8") as f:
            saved = [e["body"]["id"] for e in json.load(f).get("outbox", [])]
        self.on_disk.append(body["id"] in saved)
        self.sent.append(body)
        return self.answer.get(body["action"], {"ok": True, "id": body["id"]})

    def on_reply(self, s, entry, reply):
        self.applied.append((entry["body"]["action"], reply))


def saved_outbox():
    with open(c.STATE_FILE, encoding="utf-8") as f:
        return json.load(f).get("outbox", [])


s = c.load_state()
s["tick"] = 50
c.save_state(s)

print("1. waking up at Spike's fir, which his own town doesn't have")
s["location"] = "fir"
PLAN.update(action="go", target="junkyard")
s = c.run_tick(s)
decision = next((p for p in PROMPTS if '"action"' in p), "")
check("Spike's home" in decision, "his turn knows what the fir is")
check(s["location"] == "junkyard", "and he can fly home from it")
s["location"] = "fir"
PLAN.update(action="go", target="fir")
check(c.execute("go", "fir", s, "x").startswith("thought about going"), "going to the fir while at the fir is staying put")
s["location"] = "nest"
out = c.execute("go", "fir", s, "x")
check(s["location"] == "nest" and "couldn't find the way" in out, "his own town can't take him to the fir")
check(c.place_desc("nowhere_at_all") and c.pick_event("nowhere_at_all"), "an unknown place still has a description and events")

print("2. his own town queues nothing")
PLAN.update(action="think", target="")
s = c.run_tick(s)
check("outbox" not in s and not saved_outbox(), "no outbox at all")

print("3. save first, then send")
TOWN = c.TOWN = FakeTown()
s = c.run_tick(s)
check(len(saved_outbox()) == 2 and not TOWN.sent, "the turn saved its actions without sending them")
ids = [e["body"]["id"] for e in saved_outbox()]
c.send_outbox(s)
check(TOWN.on_disk == [True, True], "each action was already on disk when it was sent")
check([b["id"] for b in TOWN.sent] == ids, "sent with the ids that were saved")
check("outbox" not in s and not saved_outbox(), "answered actions leave the outbox (saved)")

print("4. no answer: the give waits, the rest is let go")
TOWN.sent.clear()
TOWN.answer = {"give": None, "doing": None}
s = c.run_tick(s)
give_id = next(e["body"]["id"] for e in saved_outbox() if e["body"]["action"] == "give")
c.send_outbox(s)
check([e["body"]["action"] for e in saved_outbox()] == ["give"], "only the give is still queued")
TOWN.answer = {}
TOWN.sent.clear()
c.send_outbox(s)
check([b["id"] for b in TOWN.sent] == [give_id], "and it's resent with the same id")
check(not saved_outbox(), "until it gets an answer")

print("5. a retried turn gets new ids, and a failed one sends nothing")
TOWN.sent.clear()
before = json.dumps(saved_outbox())
PLAN["broken"] = True
try:
    c.run_tick(s)
    check(False, "the failing turn raised")
except ConnectionError:
    pass
PLAN["broken"] = False
check(json.dumps(saved_outbox()) == before and not TOWN.sent, "the failed turn queued and sent nothing")
TOWN.answer = {"give": None, "doing": None}
s1 = c.run_tick(s)
first = [e["body"]["id"] for e in s1["outbox"]]
c.save_state(s)                                  # pretend that turn crashed before it was kept
time.sleep(0.01)
s2 = c.run_tick(s)
second = [e["body"]["id"] for e in s2["outbox"]]
check(first and second and not set(first) & set(second), "the same tick retried uses different ids")
s = s2

print("6. after a restart only the give is resent; old ones are given up")
c.inbox(c.TALK, "Caelan|hey")
s = c.run_step(c.reply_now, s)
check(sorted(e["body"]["action"] for e in saved_outbox()) == ["doing", "give", "say"], "a say, a doing and a give were waiting")
c.HOARD = None
s = c.load_state()                               # restart: read back what was saved
TOWN.sent.clear()
TOWN.applied.clear()
TOWN.answer = {}
c.send_outbox(s, restarted=True)
check([b["action"] for b in TOWN.sent] == ["give"], "only the give was resent")
check(sorted(a for a, r in TOWN.applied if r is None) == ["doing", "say"], "the say and the doing were let go")
check(not saved_outbox(), "nothing left waiting")
c.queue_action(s, "give", to="spike", item="old spoon")
s["outbox"][0]["t"] -= 31 * 86400
TOWN.sent.clear()
TOWN.applied.clear()
c.send_outbox(s)
check(not TOWN.sent and TOWN.applied == [("give", None)], "a give unanswered for 30 days is given up, not resent")

print("7. deliveries: each one lands in his hoard once, however many times the town shows it")
SHOWN = {"list": []}
ACKED = []


class DeliveringTown(c.LocalTown):
    name = "the delivering town"

    def deliveries(self, s):
        return None if SHOWN["list"] is None else list(SHOWN["list"])

    def ack(self, ids):
        with open(c.STATE_FILE, encoding="utf-8") as f:
            ACKED.append((list(ids), set(ids) <= set(json.load(f).get("delivered", []))))


def count(name):
    return sum(v["count"] for k, v in c.hoard()["items"].items() if k.startswith(name))


c.TOWN = DeliveringTown()
PLAN.update(action="think", target="")
SHOWN["list"] = [{"id": "d1", "item": "spinner lure", "from": "Spike", "how": "a gift from Spike"},
                 {"id": "d2", "item": "brass key", "from": "Caelan", "how": "Caelan left it for you at the lake"},
                 {"id": "d3", "item": "bottle cap", "from": "Spike", "how": "you picked it up at the lake"}]
s = c.run_tick(s)
check(count("spinner lure (from Spike)") == 1 and c.is_gift("spinner lure (from Spike)"), "a gift from Spike lands as a gift")
check(count("brass key (left by Caelan at the lake)") == 1, "something left for him lands as left by Caelan")
check(count("bottle cap") == 1 and not c.hoard()["items"]["bottle cap"]["gift"], "something he picked up is a find, not a gift")
check(not ACKED, "nothing is acked during the turn")
c.send_outbox(s)
check(ACKED and ACKED[-1][1] and sorted(ACKED[-1][0]) == ["d1", "d2", "d3"], "acked after the save, all three")
s = c.run_tick(s)                                # the ack got lost: the town shows them again
check(count("spinner lure") == 1 and count("brass key") == 1 and count("bottle cap") == 1, "shown again: nothing lands twice")
SHOWN["list"] = None                             # the town is away
s = c.run_tick(s)
check(sorted(s.get("delivered", [])) == ["d1", "d2", "d3"], "while the town is away, he keeps the ids")
SHOWN["list"] = [{"id": "d1", "item": "spinner lure", "from": "Spike", "how": "a gift from Spike"}]
s = c.run_tick(s)
check(count("spinner lure") == 1 and s.get("delivered") == ["d1"], "back again: still once, and ids the town dropped are forgotten")
SHOWN["list"] = []
s = c.run_tick(s)
check("delivered" not in s, "nothing shown: nothing remembered")

print("8. Caelan can call him to Spike's fir")


class SharedTown(c.LocalTown):
    name = "a shared town with a fir"

    def extra_places(self):
        return ["fir"]


c.TOWN = c.LocalTown()
s["location"], s["energy"] = "lake", 80
c.inbox(c.CALLS, "Caelan|fir")
s = c.run_tick(s)
check(s["location"] == "lake", "his own town has no fir: he tries and stays put")
c.TOWN = SharedTown()
c.inbox(c.CALLS, "Caelan|fir")
s = c.run_tick(s)
check(s["location"] == "fir", "with the shared town on, he flies to the fir")

print("9. he notices who's with him, and his replies know it")
WITH = {"here": []}


class CompanyTown(c.LocalTown):
    name = "a town with Spike in it"

    def here(self, loc):
        return [dict(h) for h in WITH["here"]]


def seen_lines():
    with open(c.DIARY, encoding="utf-8") as f:
        return [l for l in f.read().splitlines() if "👀" in l]


c.TOWN = CompanyTown()
PLAN.update(action="think", target="")
s["location"], s["energy"] = "fir", 80
WITH["here"] = [{"name": "Spike", "state": "asleep", "doing": None}]
s = c.run_tick(s)
check(seen_lines()[-1:] and "Spike is here at the fir, asleep" in seen_lines()[-1], "Spike asleep at the fir goes in his diary")
check(any("I saw: Spike is here at the fir, asleep" in m["text"] for m in s["memories"][-3:]), "and in his memories")
n = len(seen_lines())
s = c.run_tick(s)
check(len(seen_lines()) == n, "the same company next turn isn't noted again")
WITH["here"] = [{"name": "Spike", "state": "awake", "doing": "painting"}]
s = c.run_tick(s)
check(len(seen_lines()) == n + 1 and "Spike is awake now" in seen_lines()[-1], "he notices Spike waking up")
PROMPTS.clear()
reply = c.compose_reply(s, [("Spike", "Bolt")], {"Spike": "Bolt"}, "fir", "wind in the needles", [], [])
check("with you right now: Spike (awake, painting)" in PROMPTS[0], "a reply knows who's there with him and what they're doing")
check("Spike: a Steller's jay" in PROMPTS[0] and "Here with you now" in PROMPTS[0], "and who Spike is")
WITH["here"] = []
s = c.run_tick(s)
check("Spike left the fir" in seen_lines()[-1], "he notices Spike leaving")
WITH["here"] = [{"name": "Spike", "state": "quiet", "doing": None}]
s["location"] = "junkyard"
s = c.run_tick(s)
check("Spike is here at the junkyard, sitting quiet" in seen_lines()[-1] and "left" not in seen_lines()[-1],
      "somewhere new, he just sees who's there")
c.TOWN = c.LocalTown()
n = len(seen_lines())
s = c.run_tick(s)
PROMPTS.clear()
c.compose_reply(s, [("Caelan", "hey")], {}, "junkyard", "a dog barks", [], [])
check(len(seen_lines()) == n and "with you right now" not in PROMPTS[0], "his own town: nothing to notice, nothing added")

print("10. he's told plainly when a creature parrots him")
s["convo"] = [{"who": "Spike", "said": "Patterns tell stories, yeah.",
               "reply": "The glints and movements always tell their own tales, each one a piece of the puzzle."}]
PROMPTS.clear()
c.compose_reply(s, [("Spike", "Yeah. The glints and movements tell their own tales, each one a piece of the puzzle.")],
                {"Spike": "Yeah. The glints and movements tell their own tales, each one a piece of the puzzle."}, "junkyard", "", [], [])
check("Spike just said back almost exactly what you'd said" in PROMPTS[0], "an echo is pointed out")
PROMPTS.clear()
c.compose_reply(s, [("Spike", "Found a beetle under the fir log, ate it cold.")],
                {"Spike": "Found a beetle under the fir log, ate it cold."}, "junkyard", "", [], [])
check("said back" not in PROMPTS[0], "real news isn't called an echo")

print("11. he knows who Spike is when people talk about him without naming him")


def reply_prompt(who, said):
    PROMPTS.clear()
    c.compose_reply(s, [(who, said)], {}, "junkyard", "a dog barks", [], [])
    return PROMPTS[0]


c.remember_talk(s, [("Caelan", "hi"), ("Spike", "We mesh good.")], {"Spike": "We mesh good."}, "Yeah, we do.", "machine_shop")
check(list(s["fellows"]) == ["Spike"], "only creatures' talk is kept with them")
p = reply_prompt("Caelan", "Hey bolt! Do you like hanging out with your new friend?")
check("Spike: a Steller's jay (dark blue and black, with a tall crest), Elliott's creature, lives at the fir" in p,
      "'your new friend' brings up who Spike is")
check("You last saw him at the junkyard today at" in p and "You last talked with him today at" in p,
      "with when he last saw him and talked with him")
check('at the machine shop, Spike said "We mesh good." and you said "Yeah, we do."' in p, "and what they said, so he can have an opinion")
check("Steller's jay" in reply_prompt("Caelan", "I was talking about the jay you've been hanging with"), "'the jay' does too")
check("Steller's jay" in reply_prompt("Elliott", "what do you think of Elliott's guy?"), "so does his human's name")
check("Steller's jay" in reply_prompt("Caelan", "seen spike lately?"), "and his name, in any case")
check("Other creatures you know" not in reply_prompt("Caelan", "how's the weather up there today?"),
      "talk that isn't about him leaves him out")
PROMPTS.clear()
c.compose_reply(s, [("Spike", "found a beetle")], {"Spike": "found a beetle"}, "junkyard", "", [], [])
check("Steller's jay" in PROMPTS[0] and 'Spike said "We mesh' not in PROMPTS[0],
      "Spike talking brings it up too, without repeating their old talk (it's in his past conversations)")
s["fellows"]["Spike"].pop("lately")
s["memories"].append({"tick": s["tick"], "when": c.now(), "feeling": 1,
                      "text": 'Caelan says "yo"; Spike says "found a beetle" and I said "Nice, where?".'})
check('Spike said "found a beetle" and you said "Nice, where?"' in reply_prompt("Caelan", "how's your buddy?"),
      "talks from before he kept them come from his memories")
s["convo"] = [{"who": "Spike", "said": "x", "reply": f"Spike, the glints again {i}"} for i in range(4)]
check("spike" not in c.overused_words(s) and "glints" in c.overused_words(s), "names are never banned as crutch words")

print("12. he can start a conversation with a creature that's here")
c.TOWN = CompanyTown()
s["location"], s["energy"], s["outbox"] = "junkyard", 80, []
WITH["here"] = [{"name": "Spike", "state": "awake", "doing": None, "id": "spike"}]
PLAN.update(action="talk_to", target="Spike")
PROMPTS.clear()
s = c.run_tick(s)
decision = next((p for p in PROMPTS if '"action"' in p), "")
check("talk_to (target = Spike, here with you" in decision, "with Spike awake here, talking to him is one of his options")
says = [e["body"] for e in saved_outbox() if e["body"]["action"] == "say"]
check(says and says[-1]["to"] == "spike" and says[-1]["text"] == "Found a beetle under the old tire. Want half?",
      "what he says goes to Spike through the town")
check('said to Spike: "Found a beetle' in s["memories"][-1]["text"], "and it's his turn, in his memory")
check(s["fellows"]["Spike"]["lately"][-1]["me"].startswith("Found a beetle"), "kept with what he knows about Spike")
check('you said to Spike: "Found a beetle' in c.fellow_facts(s, [("Caelan", "how's your buddy?")], {}, []),
      "and shown as a talk he started")
WITH["here"] = [{"name": "Spike", "state": "asleep", "doing": None, "id": "spike"}]
PLAN["feel"], s["outbox"] = 2, []
PROMPTS.clear()
s = c.run_tick(s)
check("talk_to (target" not in next((p for p in PROMPTS if '"action"' in p), ""), "Spike asleep: no talk_to on offer")
check("Spike is asleep, so you let them be" in s["memories"][-1]["text"] and not saved_outbox(),
      "if he tries anyway, he lets Spike sleep and nothing is sent")
check(s["memories"][-1]["feeling"] <= 0, "and something that didn't happen can't feel like a win")
PLAN["feel"] = 0
WITH["here"] = [{"name": "Spike", "state": "awake", "doing": None, "id": "spike"}]
check("right here with you" in c.execute("go", "Spike", s, ""), "'go Spike' with Spike here: he's told Spike is right here")
WITH["here"] = []
c.notice_company(s)
out = c.execute("go", "spike", s, "")
check(out.startswith("went looking for Spike, but Spike isn't here (you last saw Spike at the junkyard"),
      "'go Spike' without him: told so, and where he last saw him")
check(c.resolve_place("Spike's fir") == "fir" and c.resolve_place("firewood pile") != "fir", "'Spike's fir' names the fir")
check("isn't here" not in c.execute("go", "Spike's fir", s, ""), "'go to Spike's fir' is still a place")
check(c.execute("talk_to", "Spike", s, "") == "wanted to talk to someone, but nobody else is here", "nobody here: nobody to talk to")
c.TOWN = c.LocalTown()

print("13. song titles keep his own words, not the model's stray Chinese")
check(c.plain_title(s, "Eternal涟漪", "lake") == "Eternal", "stray characters dropped")
check(c.plain_title(s, "涟漪", "lake") == "lake", "nothing left: the subject instead")
s["words"].append("さくら")
check(c.plain_title(s, "Spring さくら", "lake") == "Spring さくら", "a word he picked up stays")

os.chdir("/")
shutil.rmtree(WORK, ignore_errors=True)
print(f"\nPROBLEMS: {len(PROBLEMS)}")
sys.exit(1 if PROBLEMS else 0)
