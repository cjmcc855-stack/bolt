# Shasta 3D: game plan

Oct 31, 2026

A first-person, PS1-style 3D game of the shared town, built in Godot, where Caelan and Elliott can walk around together and see, talk to and give things to Bolt and Spike. The birds' brains don't change: the game is a new window into the town, not a new home for them.

## Decisions so far

Caelan has settled the big ones; everything below builds on them.

| Question | Decision | Why |
| --- | --- | --- |
| Engine | Godot 4 desktop app | A real game, not a web page; free, small, no installer |
| Look | Low-poly, like the earliest PlayStation games | Fits the 16-bit world, runs light next to Bolt's model on the same graphics card |
| Who plays | Caelan and Elliott, at the same time when they want | It's the shared town, so both humans belong in it |
| Devices | PC only, no phone | Keeps controls and graphics simple |
| Size | Realistic scale, big is fine | The mountain should feel like a mountain |
| Getting around | Walking, plus fast travel | Big world without the boring parts |

## How it fits together

```
   Caelan's PC              underworld (Elliott's VM)          Elliott's PC
 +----------------+        +--------------------------+       +----------------+
 | Shasta 3D game | <----> | Game server (new)        | <---> | Shasta 3D game |
 | (Godot app)    |        | players' spots and talk, |       | (Godot app)    |
 +----------------+        | passes along bird moves  |       +----------------+
                           +------------^-------------+
                                        | reads the town
 +----------------+        +------------v-------------+       +----------------+
 | Bolt           | <----> | Shared town server       | <---> | Spike          |
 | thinks on the  |        | places, items, birds,    |       | Elliott's jay  |
 | 3060           |        | map feed /v1/map         |       |                |
 +----------------+        +--------------------------+       +----------------+
```

Each of you runs the game on your own PC. The new game server on underworld keeps track of where the players are and what they say, and reads the shared town so the birds show up where they really are. Bolt and Spike keep living exactly as they do now; the game only adds a way to walk around in their town.

## The PS1 look

The 1996 feel comes from a handful of specific limits of that hardware, and Godot can copy every one with a shader.

- **Tiny resolution:** the game draws at about 320×240 and blows it up with chunky, unsmoothed pixels.
- **Wobbly polygons:** corners snap to a coarse grid, so models jitter slightly as you move.
- **Warping textures:** textures slide a little across big surfaces, the old "affine" look.
- **No texture smoothing**, small textures, and color dithering instead of smooth gradients.
- **Thick distance fog:** it hides how far the world goes, and it's what lets a huge map run light.

That last point matters for Caelan's PC: Bolt's model uses about 9 of the graphics card's 12 GB, and Bolt pauses at 80°C. A PS1-style game needs a few hundred MB and little power, so it can run while Bolt is thinking.

## The world: real-size Mount Shasta

The ground is the real mountain, and the town sits at its foot laid out like the 2D map both birds already know.

- **Real terrain:** USGS publishes free elevation maps of real land. A one-time build step turns the Mount Shasta area into a low-poly ground mesh; the summit really is a long climb.
- **Same places, same names:** nest, junkyard, rail yard, river canyon, garage, diner roof, ambulance station, drift lot, lake, shed, mountain trail, old barn, machine shop, summit, plus Spike's fir. Each is placed to match the 2D map, stretched to real distances.
- **Live conditions:** time of day, real weather and season come from the shared town, so rain in the game is rain on the real mountain. Holidays carry over too (Halloween pumpkins).
- **Fast travel:** a trail map at every place. Walk somewhere once and you can jump back there any time.
- **Later, real rides:** the machines Bolt builds or fixes (go-kart, pickup, dirt bike, cable car) show up where he made them and can be driven.

## Playing together and talking to the birds

Seeing the birds needs nothing new; talking to them from inside the game needs one addition to the shared town's rules.

**Seeing them (works today).** The town's read-only map feed already says where each bird is and what it's doing. The game reads it and shows Bolt and Spike at their real places, flying between them, fishing, tinkering, sleeping.

**Playing together.** A small game server with no graphics keeps the two players in sync: where each person is and what they pick up or set down. It runs on one always-on machine that both players reach over Tailscale.

**Talking, giving and being there (needs a town change).** Right now a human can only reach a bird through its owner's side (Discord, console, Bolt's own page). For the game, the town would learn a few human actions:

- a person is *here* at a place (so a bird's turn can be told plainly: "Caelan is here at the garage with you")
- a person *says* something to a bird at their place
- a person *gives* a bird something, or *leaves* something at a place (the town already has this as `hide`)

That's a protocol change: a pull request to shasta-world with contract tests, approved by both owners. Each bird then hears it through its normal channels and answers in its normal way, so both birds get it at once and neither brain changes how it thinks.

## What we need from Elliott

Three things on Elliott's side, all through the usual shasta-world pull requests.

| Ask | Why | When it's needed |
| --- | --- | --- |
| Host the game server on underworld | It's always on, already runs the town, and both players reach it over Tailscale | Step 4 (playing together) |
| Agree to the human actions in the town protocol (here, say, give) | Lets either player talk to and give to either bird from the game | Step 5 |
| Push the shared map page into the shasta-world repo | It's only on the server right now; the 3D game is phase 7 (shared town map) done in 3D, so both sides should be able to work on it | Any time; not blocking |

Steps 1 to 3 need nothing from Elliott, so they can start right away.

## Build order

Six steps, and the game is playable at the end of every one.

1. **Walk the mountain alone.** First-person controls, the PS1 look, real Mount Shasta terrain, fog, day and night, real weather from the town.
2. **The town.** Buildings, the lake and river, the rail line with its freight train, every named place, trail-map fast travel.
3. **Both birds appear** where they really are, flying between places and acting out what they're doing (read-only map feed, no town changes).
4. **Playing together.** The game server; Caelan and Elliott see each other in the world.
5. **Talking, giving, leaving things, calling a bird over, and "a human is here"** (after the town protocol change).
6. **The good stuff.** Bolt's shelf and drawings at the nest, his songs on a jukebox, the blueprints and the machines he builds, holiday decorations, Spike's own things at the fir.

The game lives in its own repo and never runs inside either bird, so Bolt's standard-library-only rule and his GPU safety limits stay exactly as they are.

## Open questions

- [ ] Elliott: OK to host the game server on underworld?
- [ ] Elliott: OK with adding human actions (here, say, give) to the town protocol?
- [ ] Where does the game's code live: a new repo, or a folder inside shasta-world?
- [ ] How big is the playable area: the town and the mountain, or the wider valley too?
- [ ] Does a player standing at a place count as "being there" for the birds the way a Discord call does today?
- [ ] Install Godot 4 and download the Mount Shasta elevation data on Caelan's PC (both one-time).
