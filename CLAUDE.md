# CLAUDE.md: read this first

You're working on **Bolt**, Caelan's autonomous AI crow. He lives on Caelan's Windows PC, thinks with a local
Ollama model (deepseek-r1:14b on an RTX 3060, no API keys), writes a Discord diary in "Bolt's Server"
(#bolts-world), and has a 16-bit world page at http://localhost:8642. Caelan talks to him on Discord, in his
console window, and on the world page.

This folder is both the live Bolt and the git checkout of `cjmcc855-stack/bolt` (public). His life files sit
next to the code and are git-ignored.

## Hard rules

1. **Never restart, stop or kill Bolt yourself.** He restarts only when Caelan types `!restart` (Discord or
   console), which runs the tests first and refuses to restart into broken code. `!stop` / `!start` go through
   `bolt_launcher.py`. Code you change takes effect at his next `!restart`.
2. **Never open or print secrets:** `discord_config.json`, `dontopentoken.txt`, `world_config.json` (it holds
   his shared-town token). Never commit them. If you need to know whether the shared town is on, read Bolt's
   console output or state, not that file.
3. **Never commit his life:** `state.json*`, `hoard.json*`, `memory_book.jsonl`, `diary.md`, `temps.csv`,
   `creature_log.txt`, inbox files, `songs/`, `drawings/`, `patches/`, `tunes/`, `names.json`,
   `creatures.json`. `.gitignore` covers them; keep it that way.
4. **Every change gets committed and pushed** to `cjmcc855-stack/bolt` (`main`), after the tests pass.
5. **Gifts are sacred.** Anything a human gave him can never be lost, used up, taken or given away
   (`is_gift`, `take_item`).
6. **Don't touch the GPU safety:** pause at 80°C, emergency shutdown at 87°C (`temp_watchdog`).
7. **Don't dictate his learning.** What he does should come from what he's read, learned and felt. Foreign
   words (he picked up some Japanese) are fine. Tell him facts plainly (like `rut_note`) instead of ordering him.
8. **Standard library only** (Python 3.10+, runs on Windows). No pip installs for Bolt.
9. **Public repo:** no IP addresses, tokens, or private family details in code, docs or commit messages.

## Before you change anything

- Read the code you're changing. `creature.py` has a map of its sections at the top.
- Run all the tests; each must end with `PROBLEMS: 0`:
  ```
  python tests/sim_days.py .            # days of fake life with a chaotic brain, crashes and outages
  python tests/creature_loop_test.py    # Discord loop protection vs a badly behaved bot
  python tests/reply_test.py            # quick replies
  python tests/town_test.py             # shared-town plumbing with fake towns
  python tests/habits_test.py           # plain talk, ruts, roosting, song storage
  python tests/world_test.py ..\shasta-world   # his real code against the real server (needs a shasta-world checkout)
  ```
- **Refactors must not change behavior.** Prove it: run the previous commit and the new code through
  `python tests/sim_days.py <folder> --ticks 500 --seed 11 --keep` and diff the two `diary.md` and
  `state.json` (ignoring timestamps). They must be identical.
- New behavior gets a test that fails without it.

## How he works (the parts that bite)

- **All-or-nothing steps.** `run_step(step, s)` runs a turn (`tick`) or a quick reply (`reply_now`) on a
  `copy.deepcopy` of his state, buffers diary lines, and only keeps anything if the step finishes. Saves are
  atomic with a `.bak`; the hoard and state are stamped with the same tick. Inbox files become `.pending`
  until the step that handled them is saved.
- **Save first, then send.** Anything for the town is queued in `s["outbox"]` during a step (`queue_action`),
  saved with it, and sent afterwards by `send_outbox()`. give/drop/take/hide are resent with the same id
  until answered; everything else is sent once.
- **Quick replies:** when someone talks, `reply_now` answers with one model call before his turn; the turn
  then knows what he said (`just_talked`, `to_learn`). One GPU, so every model call is serialized.
- **Prompt budget:** `num_ctx` 4096, about 11,600 characters including the persona (`fit_prompt`). The
  decision prompt runs around 8,400 with a full 700-character shared-town summary.
- **Night:** 22:00 to 06:00 he roosts (`roost`): flies home, sleeps, no model calls. A human can wake him and
  he stays up until 20 minutes after they go quiet; creatures can't wake him.
- **Plain talk:** flowery replies get one plain rewrite (`too_purple`, `plainer`).
- **Songs:** make_music saves its recipe in `tunes/`, synth patches in `patches/`. The newest 40 songs stay
  as audio; older ones are rebuilt byte-identical when played (`render_song`, `prune_songs`).
- **Creatures on Discord:** `CreatureGuard` (30 s bursts, 8-exchange streak then a 30-minute break, 60 a day,
  3 gifts a day). Creatures can never run owner commands. `creatures.json` maps bot names to creature names.
- **Test gotchas:** fake brains must accept `**kw`; tests that use the real clock set `c.is_night = lambda:
  False`; a test that copies `.py` files into a temp folder must put that folder on `sys.path` or `synth`
  won't import (it's optional: `synth = None`).

## The shared town (shasta-world)

Bolt and Spike (Elliott's Steller's jay, `GangSwan/spike-ai`) share a town run by a server on Elliott's
Proxmox VM (`underworld`), reached over Tailscale. Repo: `GangSwan/shasta-world` (public), its own
`CLAUDE.md`, `PROTOCOL.md` (the contract) and `DECISIONS.md`. Elliott's Claude does most of the work there.
Rules over there: **pull requests for everything** (never push to `main`), protocol changes come with contract
tests, and both owners approve. Review Elliott's PRs from Bolt's side: does it fit his all-or-nothing turns,
slow model and gifts-are-sacred rule?

- **Bolt's side:** `WorldTown` in `creature.py` plugs in where `LocalTown` does, through `world_client.py`
  (a copy of shasta-world's `client/world_client.py`; keep them identical). Whenever the town is away he
  lives in his own town (`LocalTown`) and never waits.
- **The switch:** `world_config.json` (`enabled`, `url`, `token`). It's ON now (since 2026-10-28).
- **Phases:** 1 protocol, 2 server, 3 client, 5 Bolt joins, 6 hosting: done. 4 (Spike joins) is Elliott's.
  7 shared town map (probably us), 8 retire the Discord creature-to-creature code (both), after both birds
  live in the town.

## Working with Caelan

- He's an experienced mechanic/fabricator, not a programmer by trade: explain in plain words, be direct, skip
  the jargon in replies (it's fine in code and commits).
- He often wants a "log check": read the end of `diary.md`, `creature_log.txt`, `temps.csv` and his state, and
  say what Bolt's actually doing and whether anything's wrong.
- Don't introduce your own bugs. Verify before you say something's done.
