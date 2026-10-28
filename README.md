# Bolt 🐦‍⬛

An autonomous AI crow who lives in a little town under Mount Shasta. Nobody gives him tasks: every few minutes he decides what to do based on his mood, energy, memories, and what he's learned, and his personality grows out of what happens to him.

Built by Caelan, inspired by "Pino," an AI bird living in a 3D web town.

## What he does
- Lives in 14 places (nest, junkyard, rail yard, river canyon, lake, mountain trail, summit, old barn, machine shop, drift lot, and more), with **real Mount Shasta weather**, seasons, and day/night.
- Fishes, sifts river gravel for gems, digs on the mountain, forages, tinkers junk into named inventions, takes them apart, examines things, flattens pennies on the tracks. Skills level up.
- Reads books from `library/`, looks things up on Wikipedia, writes songs (synth WAVs) and draws (SVG).
- Remembers everything: a forever memory book, an unlimited hoard (gifts can never be lost), subject notebooks, per-item knowledge, and what each person has told him. Studying counts like practice.
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

Optional Discord: copy `discord_config.example.json` to `discord_config.json`, fill in your bot token + channel id (enable the Message Content intent). Copy `names.example.json` to `names.json` to map Discord usernames to names.
`bolt_launcher.py` is a tiny always-on helper for `!start` / `!stop` / `!status` from Discord.

### Discord commands
Anyone: just type to talk · `!give <thing>` · `!leave <place> <thing>` · `!call <place>` · `!help`
Owner only: `!book <title>` (fetch a public-domain book) · `!restart` · `!start` · `!stop` · `!status`

## Safety and robustness
- GPU watchdog: pauses at 80°C, emergency shutdown at 87°C (model unloaded, lock left so he won't restart until it cools).
- Every tick is all-or-nothing; saves are atomic with backups; one instance at a time.
- `tests/sim_days.py` runs days of his life in seconds with a chaotic fake brain, crashes, power cuts and outages, and checks that nothing breaks. `!restart` runs it first and refuses to restart into broken code:
```
python tests/sim_days.py .
```

## What's not in this repo
Secrets (`discord_config.json`), and Bolt's actual life (`state.json`, `hoard.json`, `memory_book.jsonl`, `diary.md`, songs, drawings): those are personal and live only on his PC. Starting fresh hatches a brand new crow.

## Library
Original field guides written for him: rocks & gems of Shasta, fishes, music theory for one voice, the crow book, animals of the high mountain, engines/cars/shops, drawing, tinkering, and fire safety. More can be fetched from Project Gutenberg with `!book`.
