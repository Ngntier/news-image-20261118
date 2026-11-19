#!/usr/bin/env python3
"""18 November 2026 - The World in One Image.

Draws a 1024x1024 newspaper-front-page image summing up the world news
of Wednesday 18 November 2026, in pure Python 3.13 standard library.

Layout (1024 x 1024):
  masthead  y   0..104   "18 NOVEMBER 2026 - THE WORLD IN ONE IMAGE"
  panel 1   y 104..516   IRAN STRIKES KUWAIT & BAHRAIN (lead story)
  panel 2   y 516..796   XI & PUTIN MEET IN SHENZHEN (left)
  panel 3   y 516..796   KERCH BRIDGE HIT AGAIN (right)
  panel 4   y 796..924   DEMOCRATS TAKE THE SENATE
  ticker    y 924..1024  supporting stories of the day

Deterministic: no time, no randomness, no network. Two runs write
byte-identical PNGs. Output: entry.png in $MAKEFUN_OUTPUT_DIR, else
in the current directory.

Built for make.fun competition news-image-20261118.
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- framebuffer

PIX = bytearray(W * H * 3)


def px(x, y, color):
    """Set one pixel, silently clipping outside the canvas."""
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        PIX[i] = color[0]
        PIX[i + 1] = color[1]
        PIX[i + 2] = color[2]


def fill_rect(x0, y0, x1, y1, color):
    """Fill the rectangle [x0, x1) x [y0, y1) with a solid colour."""
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(W, x1)
    y1 = min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(color) * (x1 - x0)
    for y in range(y0, y1):
        i = (y * W + x0) * 3
        PIX[i:i + len(row)] = row


def rect_outline(x0, y0, x1, y1, color, t=1):
    fill_rect(x0, y0, x1, y0 + t, color)
    fill_rect(x0, y1 - t, x1, y1, color)
    fill_rect(x0, y0, x0 + t, y1, color)
    fill_rect(x1 - t, y0, x1, y1, color)


def hline(x0, x1, y, color, t=1):
    fill_rect(x0, y, x1, y + t, color)


def vline(x, y0, y1, color, t=1):
    fill_rect(x, y0, x + t, y1, color)


def disc(cx, cy, r, color):
    """Filled circle."""
    for dy in range(-r, r + 1):
        dx = int(math.sqrt(r * r - dy * dy))
        fill_rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, color)


def ring(cx, cy, r, color, t=2):
    for dy in range(-r, r + 1):
        dx = int(math.sqrt(r * r - dy * dy))
        inner = int(math.sqrt(max(0, (r - t) * (r - t) - dy * dy))) if abs(dy) < r - t else 0
        fill_rect(cx - dx, cy + dy, cx - inner, cy + dy + 1, color)
        fill_rect(cx + inner, cy + dy, cx + dx + 1, cy + dy + 1, color)


def line(x0, y0, x1, y1, color):
    """Bresenham line."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        px(x0, y0, color)
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def thick_line(x0, y0, x1, y1, color, t=3):
    """A line drawn t pixels thick (square brush along the line)."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    half = t // 2
    while True:
        fill_rect(x0 - half, y0 - half, x0 + half + 1, y0 + half + 1, color)
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def vgrad(x0, y0, x1, y1, top, bottom):
    """Vertical linear gradient over the rectangle."""
    span = max(1, y1 - y0 - 1)
    for y in range(y0, y1):
        f = (y - y0) / span
        c = (round(top[0] + (bottom[0] - top[0]) * f),
             round(top[1] + (bottom[1] - top[1]) * f),
             round(top[2] + (bottom[2] - top[2]) * f))
        fill_rect(x0, y, x1, y + 1, c)


def blend(a, b, f):
    """Linear blend of two colours, f=0 -> a, f=1 -> b."""
    return (round(a[0] + (b[0] - a[0]) * f),
            round(a[1] + (b[1] - a[1]) * f),
            round(a[2] + (b[2] - a[2]) * f))


# ---------------------------------------------------------------- palette

NAVY = (10, 24, 54)
NAVY2 = (16, 38, 78)
NAVY3 = (8, 18, 40)
GOLD = (212, 175, 55)
GOLD_LT = (232, 205, 110)
PAPER = (244, 238, 224)
WHITE = (248, 248, 244)
INK = (18, 20, 26)
RED = (178, 34, 34)
RED_LT = (214, 74, 54)
ORANGE = (232, 122, 40)
YELLOW = (244, 196, 66)


# ---------------------------------------------------------------- bitmap font
# Hand-drawn 5x7 pixel font, uppercase + digits + punctuation.
# Each glyph is 7 rows of 5 bits, "#" = on, "." = off.

_GLYPHS = {
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    '"': (".#.#.", ".#.#.", ".#.#.", ".....", ".....", ".....", "....."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    "$": ("..#..", ".####", "#.#...", ".###.", "...#.", "####.", "..#.."),
    "%": ("##..#", "##.#.", "....#", "...#.", "..#..", ".#.#.", "#..##"),
    "&": (".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"),
    "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    ",": (".....", ".....", ".....", ".....", ".##..", "..#..", ".#..."),
    "-": (".....", ".....", ".....", ".###.", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    "/": ("....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("#####", "....#", "...#.", "....#", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    ":": (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    ";": (".....", ".##..", ".##..", ".....", ".##..", "..#..", ".#..."),
    "=": (".....", ".....", "#####", ".....", "#####", ".....", "....."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "•": (".....", ".....", ".##..", ".##..", ".##..", ".....", "....."),
}

FONT = {ch: tuple(tuple(c == "#" for c in row) for row in rows)
        for ch, rows in _GLYPHS.items()}


def text_width(s, scale):
    """Pixel width of string s at the given scale (6 units per char)."""
    return len(s) * 6 * scale - scale


def draw_text(s, x, y, scale, color):
    """Draw string s with its left edge at x, top at y."""
    cx = x
    for ch in s:
        glyph = FONT.get(ch)
        if glyph is None:
            cx += 6 * scale
            continue
        for r in range(7):
            row = glyph[r]
            for c in range(5):
                if row[c]:
                    fill_rect(cx + c * scale, y + r * scale,
                              cx + (c + 1) * scale, y + (r + 1) * scale, color)
        cx += 6 * scale


def draw_text_centred(s, cx, y, scale, color):
    draw_text(s, cx - text_width(s, scale) // 2, y, scale, color)


# ---------------------------------------------------------------- PNG writer

def _chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return out


def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: None
        raw += PIX[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", ihdr)
           + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- masthead

def draw_masthead():
    fill_rect(0, 0, W, 104, NAVY)
    hline(0, W, 100, GOLD, 4)
    draw_text_centred("18 NOVEMBER 2026", W // 2, 12, 6, WHITE)
    draw_text_centred("THE WORLD IN ONE IMAGE", W // 2, 66, 2, GOLD_LT)
    disc(336, 73, 4, GOLD)
    disc(688, 73, 4, GOLD)


# ---------------------------------------------------------------- panel 1: Iran strikes Kuwait & Bahrain

def draw_panel1():
    # headline band
    fill_rect(0, 104, W, 148, NAVY2)
    draw_text_centred("IRAN STRIKES KUWAIT & BAHRAIN", W // 2, 111, 4, WHITE)
    # dusk sky over the Gulf, then the sea
    vgrad(0, 148, W, 402, (24, 30, 62), (198, 92, 42))
    vgrad(0, 402, W, 516, (14, 48, 80), (10, 32, 58))
    hline(0, W, 402, (240, 190, 120), 2)
    # low sun over the Gulf
    disc(824, 330, 34, (244, 206, 122))
    ring(824, 330, 42, (244, 206, 122), 3)
    # thin clouds
    for (cx, cy, w, h) in ((180, 210, 220, 10), (560, 240, 260, 9),
                           (880, 190, 180, 8), (420, 300, 200, 8)):
        fill_rect(cx - w // 2, cy, cx + w // 2, cy + h, (52, 48, 78))
        fill_rect(cx - w // 2 + 20, cy - 5, cx + w // 2 - 30, cy, (52, 48, 78))

    def air_base(x0, label):
        """A Gulf air base silhouette on the horizon: runway, hangar,
        control tower, radar dish."""
        base = (12, 16, 30)
        fill_rect(x0, 386, x0 + 220, 402, base)            # ground strip
        fill_rect(x0 + 10, 356, x0 + 70, 402, base)        # hangar
        disc(x0 + 40, 356, 30, base)                       # hangar roof
        fill_rect(x0 + 88, 340, x0 + 104, 402, base)       # tower
        fill_rect(x0 + 80, 330, x0 + 112, 342, base)       # tower cab
        fill_rect(x0 + 128, 366, x0 + 136, 402, base)      # radar mast
        disc(x0 + 132, 358, 12, base)                      # radar dish
        line(x0 + 132, 358, x0 + 150, 344, base)
        fill_rect(x0 + 150, 380, x0 + 210, 402, base)      # depot block
        draw_text_centred(label, x0 + 110, 414, 2, (220, 225, 235))

    air_base(56, "KUWAIT")
    air_base(748, "BAHRAIN")

    # incoming drones: dark diamonds with red trails
    def drone(x, y, tx, ty):
        thick_line(x + 14, y - 6, tx, ty, RED_LT, 3)
        fill_rect(x - 9, y - 2, x + 10, y + 3, INK)
        fill_rect(x - 2, y - 9, x + 3, y + 10, INK)
        disc(x, y, 3, RED_LT)

    drone(300, 210, 180, 372, )
    drone(430, 180, 250, 366)
    drone(620, 230, 830, 368)
    drone(700, 190, 880, 372)
    drone(520, 260, 760, 380)

    # interceptor streaks rising from the bases
    thick_line(150, 386, 260, 250, (240, 240, 230), 2)
    thick_line(190, 386, 320, 270, (240, 240, 230), 2)
    thick_line(840, 386, 740, 250, (240, 240, 230), 2)

    # explosion bursts where the strikes land
    def burst(cx, cy, r):
        disc(cx, cy, r, ORANGE)
        disc(cx, cy, int(r * 0.62), YELLOW)
        disc(cx, cy, int(r * 0.34), (255, 240, 180))
        for ang in range(0, 360, 45):
            ex = cx + int(r * 1.7 * math.cos(math.radians(ang)))
            ey = cy + int(r * 1.7 * math.sin(math.radians(ang)))
            thick_line(cx, cy, ex, ey, ORANGE, 3)

    burst(180, 372, 22)
    burst(880, 376, 20)
    burst(268, 386, 12)

    # caption band: what was reported, not confirmed damage
    fill_rect(0, 458, W, 516, (8, 14, 32))
    draw_text_centred("IRAN HITS GULF BASES HOSTING U.S. FORCES", W // 2, 466, 2, WHITE)
    draw_text_centred("KUWAIT AND BAHRAIN SAY ATTACKS INTERCEPTED", W // 2, 488, 2, GOLD_LT)


# ---------------------------------------------------------------- panel 2: Xi & Putin in Shenzhen

def draw_panel2():
    x0, x1 = 0, 512
    # headline band, two lines
    fill_rect(x0, 516, x1, 572, NAVY2)
    draw_text_centred("XI & PUTIN MEET", (x0 + x1) // 2, 521, 3, WHITE)
    draw_text_centred("IN SHENZHEN", (x0 + x1) // 2, 545, 3, GOLD_LT)
    # bright daytime sky over the Shenzhen skyline
    vgrad(x0, 572, x1, 796, (150, 186, 214), (222, 230, 234))
    disc(430, 620, 24, (244, 220, 140))
    # skyline towers with lit windows
    towers = ((18, 640, 46, 796), (72, 610, 44, 796), (124, 660, 40, 796),
              (172, 596, 52, 796), (232, 648, 42, 796), (282, 620, 46, 796),
              (336, 668, 40, 796), (384, 606, 48, 796), (440, 650, 44, 796))
    for (tx, ty, tw, tb) in towers:
        fill_rect(tx, ty, tx + tw, tb, (44, 62, 92))
        for wy in range(ty + 14, tb - 12, 22):
            for wx in (tx + 8, tx + tw - 14):
                fill_rect(wx, wy, wx + 6, wy + 8, (250, 220, 120))
    # spire on the tallest tower
    fill_rect(192, 566, 196, 596, (44, 62, 92))
    # two flag poles in front of the skyline
    vline(150, 640, 742, (240, 240, 235), 3)
    vline(330, 640, 742, (240, 240, 235), 3)
    # China flag: red field, five yellow stars
    fill_rect(153, 640, 223, 686, (222, 32, 32))
    disc(168, 654, 6, YELLOW)
    for (sx, sy) in ((188, 648), (194, 660), (188, 672), (176, 668)):
        disc(sx, sy, 3, YELLOW)
    # Russia flag: white / blue / red horizontal stripes
    fill_rect(333, 640, 403, 655, (245, 245, 245))
    fill_rect(333, 655, 403, 671, (0, 60, 160))
    fill_rect(333, 671, 403, 686, (210, 20, 30))
    # two leaders shaking hands, silhouettes on a pale dais
    fill_rect(120, 742, 392, 796, (226, 228, 230))
    disc(212, 700, 13, INK)                    # Xi head
    fill_rect(196, 712, 228, 742, INK)         # Xi body
    disc(300, 700, 13, INK)                    # Putin head
    fill_rect(284, 712, 316, 742, INK)         # Putin body
    thick_line(226, 726, 256, 736, INK, 4)     # Xi arm
    thick_line(286, 726, 256, 736, INK, 4)     # Putin arm
    disc(256, 736, 5, GOLD)                    # handshake
    # caption strip
    fill_rect(x0, 752, x1, 796, (8, 14, 32))
    draw_text_centred("AHEAD OF TRUMP TRILATERAL", (x0 + x1) // 2, 758, 2, WHITE)
    draw_text_centred("TRUMP FLIES IN VIA MANILA", (x0 + x1) // 2, 776, 2, GOLD_LT)


# ---------------------------------------------------------------- panel 3: Kerch Bridge hit again

def draw_panel3():
    x0, x1 = 512, 1024
    fill_rect(x0, 516, x1, 572, NAVY2)
    draw_text_centred("KERCH BRIDGE", (x0 + x1) // 2, 521, 3, WHITE)
    draw_text_centred("HIT AGAIN", (x0 + x1) // 2, 545, 3, GOLD_LT)
    # grey dawn sky, dark strait below
    vgrad(x0, 572, x1, 660, (120, 128, 140), (196, 178, 150))
    vgrad(x0, 660, x1, 796, (34, 62, 92), (22, 44, 70))
    for y in range(668, 796, 14):
        hline(x0 + 20, x1 - 20, y, (52, 86, 118), 2)
    # bridge deck: solid on both sides, the middle span sagging into the sea
    deck = (200, 204, 208)
    fill_rect(x0 + 8, 640, 700, 652, deck)
    fill_rect(836, 640, x1 - 8, 652, deck)
    thick_line(700, 640, 768, 706, deck, 10)   # left half of the broken span
    thick_line(768, 706, 836, 640, deck, 10)   # right half of the broken span
    # bridge pillars, one snapped
    for px0 in (560, 640, 880, 960):
        fill_rect(px0, 652, px0 + 10, 720, (150, 154, 158))
    fill_rect(760, 700, 772, 724, (150, 154, 158))
    # road markings on the standing deck
    for mx in range(x0 + 24, 692, 32):
        fill_rect(mx, 645, mx + 16, 647, YELLOW)
    for mx in range(848, x1 - 24, 32):
        fill_rect(mx, 645, mx + 16, 647, YELLOW)
    # explosion flash and smoke over the collapsed span
    disc(768, 690, 26, ORANGE)
    disc(768, 690, 15, YELLOW)
    disc(768, 690, 7, (255, 244, 200))
    smoke = ((740, 664, 26, (110, 110, 112)), (768, 636, 32, (128, 128, 130)),
             (798, 664, 24, (110, 110, 112)), (768, 604, 26, (146, 146, 148)),
             (742, 616, 18, (146, 146, 148)), (796, 612, 18, (128, 128, 130)))
    for (sx, sy, sr, sc) in smoke:
        disc(sx, sy, sr, sc)
    # caption strip
    fill_rect(x0, 752, x1, 796, (8, 14, 32))
    draw_text_centred("ROAD SPAN COLLAPSES", (x0 + x1) // 2, 758, 2, WHITE)
    draw_text_centred("SECOND DAY OF ATTACKS", (x0 + x1) // 2, 776, 2, GOLD_LT)


# ---------------------------------------------------------------- panel 4: Democrats take the Senate

def draw_panel4():
    fill_rect(0, 796, W, 924, NAVY)
    # US Capitol dome, left
    fill_rect(56, 884, 176, 892, (210, 216, 228))
    fill_rect(64, 862, 168, 884, (200, 206, 220))
    for cx in range(72, 168, 16):
        fill_rect(cx, 862, cx + 6, 884, (160, 168, 184))
    disc(116, 862, 46, (210, 216, 228))
    fill_rect(104, 812, 128, 826, (210, 216, 228))
    disc(116, 808, 5, GOLD_LT)
    fill_rect(40, 892, 192, 924, (170, 176, 192))
    # ballot box, right
    fill_rect(856, 852, 976, 924, (178, 34, 34))
    fill_rect(848, 840, 984, 856, (210, 216, 228))
    fill_rect(892, 846, 940, 850, INK)          # ballot slot
    fill_rect(896, 812, 936, 846, PAPER)        # ballot paper
    thick_line(902, 830, 910, 838, RED, 3)
    thick_line(910, 838, 928, 818, RED, 3)
    disc(976, 852, 4, GOLD)
    # headline + caption
    draw_text_centred("DEMOCRATS TAKE THE SENATE", W // 2, 808, 3, WHITE)
    draw_text_centred("PELTOLA WINS ALASKA - PROJECTED 56-44 MAJORITY",
                      W // 2, 852, 2, GOLD_LT)
    draw_text_centred("U.S. SENATE FLIPS AFTER ALASKA RESULT",
                      W // 2, 884, 2, (200, 208, 224))


# ---------------------------------------------------------------- ticker: the rest of the day

def draw_ticker():
    fill_rect(0, 924, W, 1024, NAVY3)
    hline(0, W, 924, GOLD, 3)
    draw_text_centred("ALSO TODAY: NVIDIA RECORD $115.8B REVENUE "
                      "• U.S. LOSES MEASLES-FREE STATUS", W // 2, 938, 2, WHITE)
    draw_text_centred("SIBERIA PLANE CRASH, 19 DEAD • KAHANA ELECTED SPEAKER "
                      "• EBOLA PASSES 11,000 CASES", W // 2, 968, 2, GOLD_LT)


# ---------------------------------------------------------------- compose + run

def draw_all():
    draw_masthead()
    draw_panel1()
    draw_panel2()
    draw_panel3()
    draw_panel4()
    draw_ticker()
    # panel separators
    hline(0, W, 514, PAPER, 3)
    hline(0, W, 794, PAPER, 3)
    vline(510, 516, 796, PAPER, 3)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", ".")
    os.makedirs(out_dir, exist_ok=True)
    draw_all()
    path = os.path.join(out_dir, "entry.png")
    size = write_png(path)
    print("wrote %s (%d bytes, %dx%d)" % (path, size, W, H))


if __name__ == "__main__":
    main()
