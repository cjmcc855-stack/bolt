"""Draws Bolt's Discord server icon (512x512) and a banner, as chunky original pixel art."""
import random
from PIL import Image, ImageDraw

random.seed(7)
P = 4  # each "pixel" is 4x4 real pixels on a 128x128 grid


def canvas(w, h):
    return Image.new("RGB", (w * P, h * P)), w, h


def px(d, x, y, c, w=1, h=1):
    d.rectangle([x * P, y * P, (x + w) * P - 1, (y + h) * P - 1], fill=c)


def sky_at(y, H, top, bottom):
    t = y / (H - 1)
    c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return tuple(v - (v % 6) for v in c)


def sky(d, W, H, top, bottom):
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        # banded like a 16-bit gradient
        band = tuple(v - (v % 6) for v in c)
        px(d, 0, y, band, W, 1)


def stars(d, W, H, n, ymax):
    for _ in range(n):
        x, y = random.randrange(W), random.randrange(ymax)
        px(d, x, y, random.choice([(255, 255, 255), (220, 230, 255), (255, 240, 200)]))


def mountain(d, cx, base, half, peak, W):
    """Mount Shasta-ish cone: rock, shaded east face, snow cap with a ragged edge."""
    for y in range(peak, base):
        hw = int(half * (y - peak) / (base - peak)) + 1
        for x in range(cx - hw, cx + hw + 1):
            if 0 <= x < W:
                rock = (122, 122, 138) if x < cx else (88, 88, 108)
                px(d, x, y, rock)
        snow_line = peak + int((base - peak) * 0.42) + (random.randint(-1, 1))
        if y < snow_line:
            for x in range(cx - hw, cx + hw + 1):
                if 0 <= x < W:
                    px(d, x, y, (244, 246, 251) if x < cx + 1 else (200, 210, 232))
        elif y < snow_line + 3 and random.random() < 0.6:
            for x in range(cx - hw, cx + hw + 1, 3):
                if 0 <= x < W and random.random() < 0.5:
                    px(d, x, y, (236, 240, 248))


def pine(d, x, y, s=1, col=(36, 84, 52), lite=(52, 112, 66)):
    rows = [(3, 0, 2), (2, 2, 4), (1, 4, 6), (0, 6, 8)]
    for ox, oy, w in rows:
        px(d, x + ox * s, y + oy * s, col, w * s, 2 * s)
        px(d, x + ox * s, y + oy * s, lite, max(1, w * s // 3), 2 * s)
    px(d, x + 3 * s, y + 8 * s, (90, 62, 40), 2 * s, 2 * s)


# Bolt, hi-res side profile facing right, perched
CROW = [
    "..................KKKK..........",
    "................KKKKKKK.........",
    "...............KKKKKKKKK........",
    "..............KKKKKKKWEKBB......",
    "..............KKKKKKKKKKBBBB....",
    "..............KKKKKKKKKBBBBBB...",
    "...............KKKKKKKKBBB......",
    "..............KKKKKKKKKK........",
    "............KKKKKKKKKKKK........",
    "..........KKKKkkKKKKKKKK........",
    "........KKKKkkkkKKKKKKKK........",
    "......KKKKkkkkkkKKKKKKKK........",
    "....KKKKKkkkkkkkKKKKKKK.........",
    "..KKKKKKKKkkkkkkKKKKKKK.........",
    "KKKKKKKKKKKkkkkKKKKKKK..........",
    ".KKKKKKKKKKKKKKKKKKKK...........",
    "...KKKKKKKKKKKKKKKKK............",
    ".....KKKKKKKKKKKKK..............",
    "..........KKKKKKK...............",
    "...........O...O................",
    "...........O...O................",
    "..........OOO.OOO...............",
]
PAL = {"K": (20, 20, 30), "k": (58, 72, 128), "B": (70, 70, 80), "W": (255, 255, 255), "E": (20, 20, 30), "O": (150, 140, 130)}


def crow(d, x0, y0, scale, rim=(255, 190, 140)):
    h, w = len(CROW), len(CROW[0])
    at = lambda x, y: 0 <= y < h and 0 <= x < w and CROW[y][x] in PAL
    for y in range(h):
        for x in range(w):
            ch = CROW[y][x]
            if ch in PAL:
                c = PAL[ch]
                if ch == "K" and not at(x, y - 1):          # warm sunset rim light along his top edge
                    c = (96, 70, 74)
                px(d, x0 + x * scale, y0 + y * scale, c, scale, scale)


def sparkle(d, x, y, c=(255, 230, 110)):
    px(d, x, y - 2, c, 1, 5)
    px(d, x - 2, y, c, 5, 1)
    px(d, x, y, (255, 255, 255))


# ---------------- icon ----------------
img, W, H = canvas(128, 128)
d = ImageDraw.Draw(img)
sky(d, W, H, (24, 30, 64), (240, 150, 110))          # dusk over the mountain
stars(d, W, H, 26, 40)
d.ellipse([94 * P, 12 * P, 104 * P, 22 * P], fill=(250, 244, 214))   # crescent moon
d.ellipse([97 * P, 10 * P, 107 * P, 20 * P], fill=sky_at(15, 128, (24, 30, 64), (240, 150, 110)))
mountain(d, 64, 98, 62, 26, W)
for x in range(-4, W, 9):                              # treeline
    pine(d, x + random.randint(-1, 1), 82 + random.randint(0, 4), 2)
px(d, 0, 100, (32, 56, 44), W, 28)                     # ground
for x in range(0, W, 3):
    px(d, x, 100, (46, 82, 58), 2, 1)
# branch of his dead pine
px(d, 22, 96, (106, 80, 64), 84, 4)
px(d, 22, 96, (138, 106, 84), 84, 1)
px(d, 96, 92, (106, 80, 64), 3, 5)
crow(d, 30, 52, 2)                                     # Bolt, perched on his branch
sparkle(d, 98, 86)                                     # a little shiny find
sparkle(d, 28, 88, (200, 230, 255))
img.save("/home/claude/art/bolts_server_icon.png")

# ---------------- banner (960x540, Discord's banner shape) ----------------
img, W, H = canvas(240, 135)
d = ImageDraw.Draw(img)
sky(d, W, H, (24, 30, 64), (240, 150, 110))
stars(d, W, H, 60, 50)
d.ellipse([194 * P, 14 * P, 204 * P, 24 * P], fill=(250, 244, 214))
d.ellipse([197 * P, 12 * P, 207 * P, 22 * P], fill=sky_at(17, 135, (24, 30, 64), (240, 150, 110)))
mountain(d, 120, 104, 92, 22, W)
for x in range(-4, W, 9):
    pine(d, x + random.randint(-1, 1), 88 + random.randint(0, 4), 2)
px(d, 0, 106, (32, 56, 44), W, 29)
for x in range(0, W, 3):
    px(d, x, 106, (46, 82, 58), 2, 1)
px(d, 150, 102, (106, 80, 64), 70, 4)
px(d, 150, 102, (138, 106, 84), 70, 1)
crow(d, 156, 80, 1)
sparkle(d, 210, 96)
img.save("/home/claude/art/bolts_world_banner.png")
print("ok")
