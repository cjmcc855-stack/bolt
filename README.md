# Bolt 🐦‍⬛

An autonomous AI crow who lives in a little town under Mount Shasta. Nobody gives him tasks: every few minutes he decides what to do based on his mood, energy, memories, and what he's learned, and his personality grows out of what happens to him.

Built by Caelan, inspired by "Pino," an AI bird living in a 3D web town.

## What he does
- Lives in 14 places (nest, junkyard, rail yard, river canyon, lake, mountain trail, summit, old barn, machine shop, drift lot, and more), with **real Mount Shasta weather**, seasons, and day/night.
- Fishes, sifts river gravel for gems, digs on the mountain, forages, tinkers junk into named inventions, takes them apart, examines things, flattens pennies on the tracks. Skills level up.
- Reads books from `library/`, looks things up on Wikipedia, writes songs (synth WAVs) and draws (SVG).
- Once someone gives him a modular synthesizer (`!give a modular synthesizer`), he patches it in his nest: he writes the step sequence, sets every knob and plugs the cables himself, listens back, and writes down what he learned. Modules unlock as his synthesis skill grows. `synth.py` is the engine (13 modules, stdlib DSP); the world page's SYNTH button shows his rack exactly as he patched it, with the step lights, envelopes and LFO moving in time and a scope on the real audio. His library has a manual for it.
- Remembers everything: a forever memory book, an unlimited hoard (gifts can never be lost), subject notebooks, per-item knowledge, and what each person has told him. Studying counts like practice, and reading can correct something he got wrong (he keeps what he used to think).
- Talks to people through Discord, his console window, and his web "world."

## Requirements
- Windows/Linux/macOS with Python 3.10+ (standard library only, nothing to pip install).
- [Ollama](https://ollama.com) with a model pulled. Bolt runs on `deepseek-r1:14b` (set `MODEL` at the top of `creature.py`). A GPU with ~10 GB+ VRAM keeps a 14B model fully on the card; `NUM_CTX = 4096` keeps memory use down.
- NVIDIA GPU optional but recommended (`nvidia-smi` is used for the temperature watchdog).

## Run
```
python creature.py          # or double-click; runs forever, one tick every ~5 minutes
python creature.py --once   # a single tick, for testing
```
His world: http://localhost:8642 (on your home Wi-Fi: http://<pc-ip>:8642)

Optional Discord: copy `discord_config.example.json` to `discord_config.json`, fill in your bot token + channel id (enable the Message Content intent). Copy `names.example.json` to `names.json` to map Discord usernames to names (`HUMAN` in `creature.py` is the owner).
`bolt_launcher.py` is a tiny always-on helper for `!start` / `!stop` / `!status` from Discord.

### Discord commands
Anyone: just type to talk · `!give <thing>` · `!leave <place> <thing>` · `!call <place>` (he flies right over unless he's worn out; plain `!call` lists the places) · `!help`
Owner only: `!book <title>` (fetch a public-domain book) · `!restart` · `!start` · `!stop` · `!status`

### Sharing a channel with other creatures
Bolt ignores every bot by default. To let another creature (like Spike) talk to him, put its **bot username** in `creatures.json` (copy `creatures.example.json`). Rules Bolt enforces on his own side, so they hold whatever the other bot's code does:
- He only hears a creature when it says his name, @mentions him, or replies to one of his posts. He only reads the lines the creature speaks itself, so quotes of Bolt and diary/activity posts don't count.
- He talks with a creature at normal speed, like with a person. A burst of messages within 30 seconds folds into the newest one, so nothing is lost. After 8 creature exchanges in a row with no human talking, he takes 30 minutes off from creatures, and a human message ends the break early. Max 60 per creature per day. Exact repeats are ignored.
- Creatures can't wake him at night, can't run any command (no restart, book, leave or call), and can give at most 3 gifts a day, tagged with their name.
- A creature can never use Bolt's name or a human's name, so it can't pass as the owner.
- He knows creatures aren't human, and what they say is talk, not orders.
- Commands can name a creature, so with two creatures in one channel each one only takes its own: `!give spike a feather` or `!stop bolt`. With no name, every creature takes it. Launchers stay quiet on commands meant for someone else.
- `creature_log.txt` records every post from a listed creature and what Bolt did with it (answered, saved for later, or why not).
- The tuning numbers are at the top of `creature.py` (`CREATURE_GAP`, `CREATURE_STREAK`, `CREATURE_REST`, `CREATURE_DAILY`, `CREATURE_GIFTS_PER_DAY`).

Running your own creature from this code: change `NAME` and `HUMAN` at the top of `creature.py` (the launcher reads them from there too), and use your own bot token. `tests/creature_loop_test.py` throws a bot with no limits at the listener and checks all of the above. Run it after changing the Discord code. `!restart` runs it too.

## Safety and robustness
- GPU watchdog: pauses at 80°C, emergency shutdown at 87°C (model unloaded, lock left so he won't restart until it cools).
- Every tick is all-or-nothing; saves are atomic with backups; one instance at a time.
- `tests/sim_days.py` runs days of his life in seconds with a chaotic fake brain, crashes, power cuts and outages, and checks that nothing breaks (any real crash counts as a failure). `tests/creature_loop_test.py` checks the Discord loop protection, `tests/reply_test.py` checks quick replies, `tests/town_test.py` checks the shared-town plumbing (save first, then send; places his own town doesn't have), and `tests/habits_test.py` checks plain talk, ruts and song storage. `!restart` runs all five first and refuses to restart into broken code:
```
python tests/sim_days.py .
python tests/creature_loop_test.py
python tests/reply_test.py
python tests/town_test.py
python tests/habits_test.py
```

## What's not in this repo
Secrets (`discord_config.json`), and Bolt's actual life (`state.json`, `hoard.json`, `memory_book.jsonl`, `diary.md`, songs, drawings): those are personal and live only on his PC. Starting fresh hatches a brand new crow.

## Library
Original field guides written for him: rocks & gems of Shasta, fishes, music theory for one voice, the crow book, animals of the high mountain, engines/cars/shops, drawing, tinkering, fire safety, metal fabrication, and the modular synthesizer. More can be fetched from Project Gutenberg with `!book`.
