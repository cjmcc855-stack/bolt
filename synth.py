"""
synth.py - Bolt's modular synthesizer. A semi-modular rack: the main signal path is wired behind the panel
("normalled"), and patch cables add modulation on top. Bolt designs a patch (knobs + cables + a step sequence),
and render() plays it into a WAV file. Standard library only.

THE RACK (left to right), and what's wired behind the panel:
  SEQ    16-step sequencer      pitch -> VCO 1 + VCO 2,  gate -> ENV 1 + ENV 2
  VCO 1  oscillator             -> MIXER
  VCO 2  oscillator             -> MIXER
  NOISE  noise source           -> MIXER
  MIXER  3-channel mixer        -> VCF
  VCF    resonant filter        -> VCA          (ENV 2 opens it, by the VCF's ENV knob)
  ENV 1  amp envelope (ADSR)    -> VCA level
  ENV 2  filter envelope (ADSR) -> VCF cutoff
  VCA    amplifier              -> DELAY
  LFO    slow oscillator        (only does something when you patch a cable from it)
  DELAY  echo                   -> REVERB
  REVERB room                   -> OUT
  OUT    master volume

Patch cables (up to 6) run from an output to a modulation input, with an amount from -1 to +1:
  outputs: lfo.out, env1.out, env2.out, noise.out, vco2.out
  inputs:  vco1.pitch, vco2.pitch, vco1.pw, vcf.cutoff, vcf.resonance, vca.level, delay.time
"""
import math, random, struct, wave, zlib

SR = 22050
MAX_SECONDS = 24
TAIL_SECONDS = 2.0
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10], "lydian": [0, 2, 4, 6, 7, 9, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "pentatonic": [0, 2, 4, 7, 9], "minor pentatonic": [0, 3, 5, 7, 10], "blues": [0, 3, 5, 6, 7, 10],
    "chromatic": list(range(12)),
}
WAVES = ["saw", "square", "triangle", "sine"]
LFO_WAVES = ["sine", "triangle", "square", "saw", "random"]
FILTER_MODES = ["lowpass", "bandpass", "highpass"]
CABLE_SOURCES = ["lfo.out", "env1.out", "env2.out", "noise.out", "vco2.out"]
CABLE_DESTS = ["vco1.pitch", "vco2.pitch", "vco1.pw", "vcf.cutoff", "vcf.resonance", "vca.level", "delay.time"]
MAX_CABLES = 6

# every knob: (default, low, high). Choices are lists.
KNOBS = {
    "seq":    {"glide": (0.0, 0, 1), "gate": (0.5, 0.05, 1)},
    "vco1":   {"wave": WAVES, "octave": (0, -2, 2), "fine": (0.0, -1, 1), "pw": (0.5, 0.05, 0.95)},
    "vco2":   {"wave": WAVES, "octave": (0, -2, 2), "fine": (0.0, -1, 1)},
    "noise":  {"color": ["white", "pink"]},
    "mixer":  {"vco1": (0.8, 0, 1), "vco2": (0.0, 0, 1), "noise": (0.0, 0, 1)},
    "vcf":    {"mode": FILTER_MODES, "cutoff": (0.55, 0, 1), "resonance": (0.2, 0, 1), "env": (0.4, 0, 1),
               "drive": (0.1, 0, 1), "track": (0.5, 0, 1)},
    "env1":   {"attack": (0.02, 0, 1), "decay": (0.3, 0, 1), "sustain": (0.6, 0, 1), "release": (0.3, 0, 1)},
    "env2":   {"attack": (0.02, 0, 1), "decay": (0.35, 0, 1), "sustain": (0.2, 0, 1), "release": (0.3, 0, 1)},
    "vca":    {"level": (0.8, 0.2, 1)},          # never fully closed: a silent song isn't a song
    "lfo":    {"wave": LFO_WAVES, "rate": (0.4, 0, 1)},
    "delay":  {"time": (0.35, 0, 1), "feedback": (0.35, 0, 1), "tone": (0.5, 0, 1), "mix": (0.0, 0, 1)},
    "reverb": {"size": (0.5, 0, 1), "damp": (0.5, 0, 1), "mix": (0.0, 0, 1)},
    "out":    {"volume": (0.8, 0, 1)},
}
# What Bolt can use at each synthesis level (practice + study). Locked modules sit in the rack, switched off.
UNLOCKS = [(0, ["seq", "vco1", "mixer", "vcf", "env1", "env2", "vca", "out"]), (1, ["lfo"]), (2, ["vco2", "noise"]),
           (3, ["delay"]), (4, ["reverb"]), (5, ["advanced cables"])]
MODULE_ORDER = ["seq", "vco1", "vco2", "noise", "mixer", "vcf", "env1", "env2", "vca", "lfo", "delay", "reverb", "out"]


def unlocked(level):
    out = []
    for need, mods in UNLOCKS:
        if level >= need:
            out += mods
    return out


def _num(v, default, lo, hi):
    try:
        v = float(v)
        if math.isnan(v) or math.isinf(v):
            raise ValueError
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _choice(v, options, default):
    v = str(v or "").strip().lower()
    return v if v in options else default


def sanitize(raw, level=10):
    """Whatever the model sends, returns a complete, playable patch. Locked modules are switched off."""
    raw = raw if isinstance(raw, dict) else {}
    mods_in = raw.get("modules") if isinstance(raw.get("modules"), dict) else {}
    have = set(unlocked(level))
    p = {"title": str(raw.get("title") or "untitled patch").strip()[:40] or "untitled patch",
         "bpm": int(_num(raw.get("bpm"), 100, 50, 170)),
         "division": 16 if str(raw.get("division")) == "16" else 8}
    root = str(raw.get("root") or "A").strip().upper()
    root = FLATS.get(root, root)
    p["root"] = root if root in NOTE_NAMES else "A"
    p["scale"] = _choice(raw.get("scale"), SCALES, "minor")
    p["octave"] = int(_num(raw.get("octave"), 3, 1, 5))
    steps = raw.get("steps") if isinstance(raw.get("steps"), list) else []
    clean = []
    for s in steps[:16]:
        if s is None or (isinstance(s, str) and s.strip().lower() in ("rest", "-", "", "none", "null")):
            clean.append(None)
        else:
            try:
                clean.append(int(max(-7, min(14, round(float(s))))))
            except (TypeError, ValueError):
                clean.append(None)
    if all(x is None for x in clean):
        clean = [0, None, 2, 4, None, 4, 2, None]          # nothing playable: a simple default phrase
    while len(clean) < 8:
        clean.append(None)
    p["steps"] = clean
    modules = {}
    for m, knobs in KNOBS.items():
        src = mods_in.get(m) if isinstance(mods_in.get(m), dict) else {}
        out = {}
        for k, spec in knobs.items():
            if isinstance(spec, list):
                out[k] = _choice(src.get(k), spec, spec[0])
            else:
                d, lo, hi = spec
                out[k] = _num(src.get(k), d, lo, hi)
                if k == "octave":
                    out[k] = int(round(out[k]))
        modules[m] = out
    if "vco2" not in have:
        modules["mixer"]["vco2"] = 0.0
    if "noise" not in have:
        modules["mixer"]["noise"] = 0.0
    if "delay" not in have:
        modules["delay"]["mix"] = 0.0
    if "reverb" not in have:
        modules["reverb"]["mix"] = 0.0
    if modules["mixer"]["vco1"] + modules["mixer"]["vco2"] + modules["mixer"]["noise"] < 0.05:
        modules["mixer"]["vco1"] = 0.8                     # a silent mixer isn't a song
    p["modules"] = modules
    cables, seen = [], set()
    allowed_src = {"lfo.out"} if "lfo" in have else set()
    if "advanced cables" in have:
        allowed_src |= set(CABLE_SOURCES)
    elif "vco2" in have:
        allowed_src |= {"env2.out"}
    for c in (raw.get("cables") if isinstance(raw.get("cables"), list) else [])[:12]:
        if not isinstance(c, dict):
            continue
        frm, to = str(c.get("from", "")).strip().lower(), str(c.get("to", "")).strip().lower()
        if frm not in allowed_src or to not in CABLE_DESTS or (frm, to) in seen:
            continue
        if frm == "vco2.out" and to == "vco2.pitch":
            continue                                       # a VCO can't modulate itself here
        seen.add((frm, to))
        cables.append({"from": frm, "to": to, "amount": round(_num(c.get("amount"), 0.5, -1, 1), 3)})
        if len(cables) >= MAX_CABLES:
            break
    p["cables"] = cables
    p["level"] = level
    return p


def note_freqs(p):
    scale = SCALES[p["scale"]]
    base = 12 * (p["octave"] + 1) + NOTE_NAMES.index(p["root"])
    out = []
    for d in p["steps"]:
        if d is None:
            out.append(None)
        else:
            octv, idx = divmod(d, len(scale))
            out.append(base + 12 * octv + scale[idx])
    return out


def timing(p):
    step = 60.0 / p["bpm"] / (2 if p["division"] == 8 else 4)
    loop = step * len(p["steps"])
    repeats = max(1, min(16, int(round(18.0 / loop))))
    while loop * repeats > MAX_SECONDS - TAIL_SECONDS and repeats > 1:
        repeats -= 1
    return step, repeats


def _time(x, lo, hi):
    return lo * (hi / lo) ** x


class _Env:
    __slots__ = ("a", "d", "s", "r", "stage", "v", "rel_step")

    def __init__(self, k):
        self.a = 1.0 / max(1, _time(k["attack"], 0.001, 2.0) * SR)
        self.d = _time(k["decay"], 0.005, 3.0) * SR
        self.s = k["sustain"]
        self.r = _time(k["release"], 0.005, 3.0) * SR
        self.stage, self.v, self.rel_step = 0, 0.0, 0.0       # 0 idle, 1 attack, 2 decay, 3 sustain, 4 release

    def gate_on(self):
        self.stage = 1

    def gate_off(self):
        if self.stage:
            self.stage, self.rel_step = 4, max(self.v, 1e-4) / self.r

    def tick(self):
        st = self.stage
        if st == 1:
            self.v += self.a
            if self.v >= 1.0:
                self.v, self.stage = 1.0, 2
        elif st == 2:
            self.v -= (1.0 - self.s) / self.d
            if self.v <= self.s:
                self.v, self.stage = self.s, 3
        elif st == 4:
            self.v -= self.rel_step
            if self.v <= 0.0:
                self.v, self.stage = 0.0, 0
        return self.v


def _blep(t, dt):
    if t < dt:
        t /= dt
        return t + t - t * t - 1.0
    if t > 1.0 - dt:
        t = (t - 1.0) / dt
        return t * t + t + t + 1.0
    return 0.0


LAST_STATS = {}


def _listen(out, peak, p, play_secs):
    """What the patch actually sounded like, in plain words: what a crow would notice listening back."""
    n = len(out)
    norm = [v / peak for v in out[: int(play_secs * SR)] or out]
    energy = sum(v * v for v in norm) or 1e-9
    rms = (energy / len(norm)) ** 0.5
    edge = sum((b - a) * (b - a) for a, b in zip(norm, norm[1:]))
    hz = SR / (2 * math.pi) * (edge / energy) ** 0.5       # "average frequency" of the sound: how bright it is
    win = SR // 20                                      # loudness every 50 ms
    lv = [max(abs(v) for v in norm[i:i + win]) for i in range(0, len(norm) - win, win)]
    loud = sum(1 for v in lv if v > 0.25) / max(1, len(lv))
    after = out[int((play_secs + 0.4) * SR):]          # skip the last note's own release
    tail = (sum(v * v for v in after) / max(1, len(after))) ** 0.5 / peak / max(rms, 1e-6) if after else 0.0
    notes = sum(1 for x in p["steps"] if x is not None) / (len(p["steps"]) * 60.0 / p["bpm"] / (2 if p["division"] == 8 else 4))
    return {
        "brightness": "very bright and buzzy" if hz > 2500 else "bright" if hz > 1000 else "warm" if hz > 400 else "soft, dark and round",
        "body": "full and loud the whole time" if rms > 0.35 else "solid" if rms > 0.2 else "thin and plucky" if rms > 0.08 else "sparse, mostly quiet",
        "shape": "it rings out between notes" if loud > 0.6 else "short notes with gaps" if loud < 0.3 else "notes with some space",
        "tail": "a long echo/reverb tail after the end" if tail > 0.15 else "it stops clean",
        "busy": "fast and busy" if notes > 5 else "steady" if notes > 2 else "slow and spacious",
        "brightness_hz": int(hz), "rms": round(rms, 3), "seconds": round(n / SR, 1),
    }


def render(patch, path, level=10):
    """Plays the patch and writes a mono 16-bit WAV. Returns (seconds, patch actually played)."""
    p = sanitize(patch, level)
    M = p["modules"]
    step, repeats = timing(p)
    p["timing"] = {"step": step, "repeats": repeats}     # so the rack view can light the steps in time
    notes = note_freqs(p)
    n_steps = len(notes) * repeats
    total = int((step * n_steps + TAIL_SECONDS) * SR)
    gate_len = M["seq"]["gate"]
    glide_coef = 1.0 - math.exp(-1.0 / max(1.0, _time(M["seq"]["glide"], 0.001, 0.4) * SR)) if M["seq"]["glide"] > 0.01 else 1.0

    # cable amounts by destination
    mod = {d: [] for d in CABLE_DESTS}
    for c in p["cables"]:
        mod[c["to"]].append((c["from"], c["amount"]))

    v1, v2 = M["vco1"], M["vco2"]
    w1, w2 = WAVES.index(v1["wave"]), WAVES.index(v2["wave"])
    off1, off2 = 12 * v1["octave"] + v1["fine"], 12 * v2["octave"] + v2["fine"] + 0.07   # a hair of detune
    mx = M["mixer"]
    g1, g2, gn = mx["vco1"], mx["vco2"], mx["noise"]
    pink = M["noise"]["color"] == "pink"
    F = M["vcf"]
    fmode = FILTER_MODES.index(F["mode"])
    f_base = 30.0 * 2 ** (F["cutoff"] * 9.0)
    f_env, f_track, drive = F["env"] * 7.0, F["track"], 1.0 + F["drive"] * 5.0
    res_base = F["resonance"]
    e1, e2 = _Env(M["env1"]), _Env(M["env2"])
    vca_level = M["vca"]["level"]
    L = M["lfo"]
    lfo_w, lfo_hz = LFO_WAVES.index(L["wave"]), _time(L["rate"], 0.05, 20.0)
    D = M["delay"]
    d_time, d_fb, d_mix = _time(D["time"], 0.03, 1.0), D["feedback"] * 0.9, D["mix"]
    d_tone = 0.15 + 0.8 * D["tone"]
    dbuf = [0.0] * int(SR * 1.6)
    dlen = len(dbuf)
    R = M["reverb"]
    r_mix, r_fb, r_damp = R["mix"], 0.7 + 0.28 * R["size"], R["damp"] * 0.6
    combs = [[0.0] * n for n in (558, 594, 638, 678)]
    comb_i, comb_lp = [0, 0, 0, 0], [0.0, 0.0, 0.0, 0.0]
    aps = [[0.0] * n for n in (278, 220)]
    ap_i = [0, 0]
    out_vol = M["out"]["volume"]

    rnd = random.Random(zlib.crc32(p["title"].encode()))
    ph1 = ph2 = lfo_ph = 0.0
    lfo_hold, lfo_val = rnd.uniform(-1, 1), 0.0
    pk0 = pk1 = pk2 = 0.0
    ic1 = ic2 = 0.0                                   # filter state
    g = k = 0.0
    dw, dlp = 0, 0.0
    pitch = float(notes[0] if notes[0] is not None else 57)
    target = pitch
    samples_per_step = step * SR
    gate_samples = int(samples_per_step * gate_len)
    next_step, step_i, gate_off_at = 0, 0, -1
    out = [0.0] * total
    two_pi = 2 * math.pi
    nyq = 0.45 * SR
    srcs = {"lfo.out": 0.0, "env1.out": 0.0, "env2.out": 0.0, "noise.out": 0.0, "vco2.out": 0.0}
    has = {d: bool(v) for d, v in mod.items()}
    sin, tanh, tan, exp2 = math.sin, math.tanh, math.tan, (lambda x: 2.0 ** x)

    for i in range(total):
        # ---- sequencer ----
        if i >= next_step and step_i < n_steps:
            n = notes[step_i % len(notes)]
            if n is not None:
                target = float(n)
                e1.gate_on()
                e2.gate_on()
                gate_off_at = i + gate_samples
            step_i += 1
            next_step = int(step_i * samples_per_step)
        if i == gate_off_at:
            e1.gate_off()
            e2.gate_off()
        pitch += (target - pitch) * glide_coef

        # ---- LFO ----
        lfo_ph += lfo_hz / SR
        if lfo_ph >= 1.0:
            lfo_ph -= 1.0
            lfo_hold = rnd.uniform(-1, 1)
        if lfo_w == 0:
            lfo_val = sin(two_pi * lfo_ph)
        elif lfo_w == 1:
            lfo_val = 4.0 * lfo_ph - 1.0 if lfo_ph < 0.5 else 3.0 - 4.0 * lfo_ph
        elif lfo_w == 2:
            lfo_val = 1.0 if lfo_ph < 0.5 else -1.0
        elif lfo_w == 3:
            lfo_val = 2.0 * lfo_ph - 1.0
        else:
            lfo_val = lfo_hold
        env1 = e1.tick()
        env2 = e2.tick()
        white = rnd.random() * 2.0 - 1.0
        if pink:
            pk0 = 0.99765 * pk0 + white * 0.0990460
            pk1 = 0.96300 * pk1 + white * 0.2965164
            pk2 = 0.57000 * pk2 + white * 1.0526913
            noise = (pk0 + pk1 + pk2 + white * 0.1848) * 0.25
        else:
            noise = white
        srcs["lfo.out"], srcs["env1.out"], srcs["env2.out"], srcs["noise.out"] = lfo_val, env1, env2, noise

        # ---- VCO 2 (first: it can modulate VCO 1) ----
        semi2 = pitch + off2
        if has["vco2.pitch"]:
            for s, a in mod["vco2.pitch"]:
                semi2 += srcs[s] * a * 12.0
        dt2 = min(0.45, 440.0 * exp2((semi2 - 69.0) / 12.0) / SR)
        ph2 += dt2
        if ph2 >= 1.0:
            ph2 -= 1.0
        if w2 == 0:
            o2 = 2.0 * ph2 - 1.0 - _blep(ph2, dt2)
        elif w2 == 1:
            o2 = (1.0 if ph2 < 0.5 else -1.0) + _blep(ph2, dt2) - _blep((ph2 + 0.5) % 1.0, dt2)
        elif w2 == 2:
            o2 = 4.0 * ph2 - 1.0 if ph2 < 0.5 else 3.0 - 4.0 * ph2
        else:
            o2 = sin(two_pi * ph2)
        srcs["vco2.out"] = o2

        # ---- VCO 1 ----
        semi1 = pitch + off1
        if has["vco1.pitch"]:
            for s, a in mod["vco1.pitch"]:
                semi1 += srcs[s] * a * 12.0
        dt1 = min(0.45, 440.0 * exp2((semi1 - 69.0) / 12.0) / SR)
        ph1 += dt1
        if ph1 >= 1.0:
            ph1 -= 1.0
        if w1 == 0:
            o1 = 2.0 * ph1 - 1.0 - _blep(ph1, dt1)
        elif w1 == 1:
            pw = v1["pw"]
            if has["vco1.pw"]:
                for s, a in mod["vco1.pw"]:
                    pw += srcs[s] * a * 0.45
                pw = 0.05 if pw < 0.05 else 0.95 if pw > 0.95 else pw
            o1 = (1.0 if ph1 < pw else -1.0) + _blep(ph1, dt1) - _blep((ph1 - pw) % 1.0, dt1)
        elif w1 == 2:
            o1 = 4.0 * ph1 - 1.0 if ph1 < 0.5 else 3.0 - 4.0 * ph1
        else:
            o1 = sin(two_pi * ph1)

        # ---- mixer -> VCF ----
        x = (o1 * g1 + o2 * g2 + noise * gn) * 0.6
        if (i & 15) == 0:                             # filter coefficients at control rate (every 16 samples)
            oct_ = env2 * f_env + f_track * (pitch - 60.0) / 12.0
            if has["vcf.cutoff"]:
                for s, a in mod["vcf.cutoff"]:
                    oct_ += srcs[s] * a * 4.0
            fc = f_base * exp2(oct_)
            fc = 20.0 if fc < 20.0 else nyq if fc > nyq else fc
            res = res_base
            if has["vcf.resonance"]:
                for s, a in mod["vcf.resonance"]:
                    res += srcs[s] * a * 0.5
                res = 0.0 if res < 0.0 else 1.0 if res > 1.0 else res
            g = tan(math.pi * fc / SR)
            k = 2.0 - 1.96 * res
            a1 = 1.0 / (1.0 + g * (g + k))
        x = tanh(x * drive) / (drive ** 0.5)
        v3 = x - ic2
        v1_ = a1 * ic1 + g * a1 * v3
        v2_ = ic2 + g * v1_
        ic1, ic2 = 2.0 * v1_ - ic1, 2.0 * v2_ - ic2
        y = v2_ if fmode == 0 else v1_ if fmode == 1 else x - k * v1_ - v2_

        # ---- VCA ----
        amp = env1 * vca_level
        if has["vca.level"]:
            for s, a in mod["vca.level"]:
                amp *= 1.0 + srcs[s] * a
            amp = 0.0 if amp < 0.0 else amp
        y *= amp

        # ---- delay ----
        if d_mix > 0.0:
            t = d_time
            if has["delay.time"]:
                for s, a in mod["delay.time"]:
                    t *= 1.0 + srcs[s] * a * 0.5
            pos = dw - t * SR
            while pos < 0:
                pos += dlen
            i0 = int(pos)
            frac = pos - i0
            tap = dbuf[i0 % dlen] * (1.0 - frac) + dbuf[(i0 + 1) % dlen] * frac
            dlp += (tap - dlp) * d_tone
            dbuf[dw] = y + dlp * d_fb
            dw = dw + 1 if dw + 1 < dlen else 0
            y = y * (1.0 - d_mix * 0.5) + dlp * d_mix

        # ---- reverb (Freeverb-style: 4 combs, 2 allpasses) ----
        if r_mix > 0.0:
            acc = 0.0
            for c in range(4):
                buf, j = combs[c], comb_i[c]
                o = buf[j]
                comb_lp[c] = o * (1.0 - r_damp) + comb_lp[c] * r_damp
                buf[j] = y * 0.15 + comb_lp[c] * r_fb
                comb_i[c] = j + 1 if j + 1 < len(buf) else 0
                acc += o
            for c in range(2):
                buf, j = aps[c], ap_i[c]
                b = buf[j]
                buf[j] = acc + b * 0.5
                acc = b - acc
                ap_i[c] = j + 1 if j + 1 < len(buf) else 0
            y = y * (1.0 - r_mix * 0.5) + acc * r_mix
        out[i] = y

    peak = max(1e-6, *(abs(v) for v in out))
    LAST_STATS.clear()
    LAST_STATS.update(_listen(out, peak, p, n_steps * step))
    gain = (0.35 + 0.6 * out_vol) / peak
    frames = bytearray()
    for v in out:
        v = tanh(v * gain * 1.2) / tanh(1.2)
        frames += struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32000))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(frames))
    return total / SR, p


def describe(p):
    """One plain line about a patch, for his diary: 'saw VCO through a resonant lowpass, LFO on cutoff, ...'."""
    M = p["modules"]
    voices = [f"{M['vco1']['wave']} VCO 1"]
    if M["mixer"]["vco2"] > 0.05:
        voices.append(f"{M['vco2']['wave']} VCO 2")
    if M["mixer"]["noise"] > 0.05:
        voices.append(f"{M['noise']['color']} noise")
    res = M["vcf"]["resonance"]
    flt = ("a screaming " if res > 0.8 else "a resonant " if res > 0.5 else "a ") + M["vcf"]["mode"]
    bits = [" + ".join(voices) + f" through {flt}"]
    for c in p["cables"]:
        bits.append(f"{c['from'].split('.')[0].upper().replace('ENV', 'ENV ')} -> {c['to'].replace('.', ' ')}")
    if M["delay"]["mix"] > 0.05:
        bits.append("echo")
    if M["reverb"]["mix"] > 0.05:
        bits.append("reverb")
    return ", ".join(bits) + f"; {p['bpm']} bpm in {p['root']} {p['scale']}"
