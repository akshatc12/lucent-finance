#!/usr/bin/env python3
"""Generate Lucent's README banner — a Game Boy-style pixel sunrise.

Serene morning landscape: rising sun, sunrise sky, layered mountains, rolling
greenery and a few birds, rendered as chunky pixels on the Game Boy's own 160-
wide grid. Pure SVG (no fonts, no rasters) so it stays crisp and tiny on GitHub.

    python3 assets/make_banner.py            # writes assets/banner.svg
"""
import math
import os
import random

PX = 5                      # size of one "pixel" cell, in SVG units
COLS, ROWS = 160, 48        # 160 echoes the Game Boy screen width
W, H = COLS * PX, ROWS * PX
random.seed(7)

# ── palette ────────────────────────────────────────────────────────────────
# Sunrise sky, top → horizon (indigo night giving way to gold morning).
SKY = [
    (0, 3, "#20284d"), (3, 6, "#313c66"), (6, 9, "#41507e"), (9, 12, "#566392"),
    (12, 15, "#6f6f9c"), (15, 18, "#8a76a0"), (18, 21, "#b27f93"),
    (21, 24, "#db8f76"), (24, 27, "#f0a85f"), (27, 30, "#f9c861"),
    (30, 32, "#ffe18a"),
]
SUN_CORE, SUN_BODY, GLOW = "#fff7d6", "#ffe487", "#ffcf63"
MTN, MTN_SHADE, SNOW = "#6f6394", "#5a4f7e", "#f6d6ab"   # distant range + lit caps
HILL_FAR, HILL_MID, HILL_NEAR = "#6fa12f", "#4d8420", "#356615"
GROUND, TREE, TREE_HI, TRUNK = "#1f4310", "#357014", "#5b9420", "#3a2a14"
BIRD = "#2a2440"
INK, CREAM = "#1a1233", "#fff6e0"

out = []
def rect(c, r, w, h, fill, op=1.0):
    o = "" if op == 1 else f' opacity="{op}"'
    out.append(f'<rect x="{c*PX}" y="{r*PX}" width="{w*PX}" height="{h*PX}" fill="{fill}"{o}/>')

def ridge(base, peaks, jitter=0.0):
    """A stepped ridge line: row height per column from cosine humps + jitter."""
    line = []
    for c in range(COLS + 1):
        y = base
        for cx, amp, width in peaks:
            d = (c - cx) / width
            if abs(d) < math.pi / 2:
                y -= amp * math.cos(d)
        y += random.uniform(-jitter, jitter)
        line.append(int(round(y)))
    return line

def ridge_linear(points):
    """A jagged ridge: linear interpolation between (col,row) control points."""
    line = []
    for c in range(COLS + 1):
        for i in range(len(points) - 1):
            c0, r0 = points[i]; c1, r1 = points[i + 1]
            if c0 <= c <= c1:
                t = 0 if c1 == c0 else (c - c0) / (c1 - c0)
                line.append(int(round(r0 + (r1 - r0) * t)))
                break
        else:
            line.append(points[-1][1])
    return line

def mountain(line, fill, bottom=ROWS):
    """Filled stepped polygon from a ridge line down to `bottom`."""
    pts = [f"{0},{line[0]*PX}"]
    for c in range(COLS + 1):
        pts.append(f"{c*PX},{line[c]*PX}")
        if c < COLS:
            pts.append(f"{(c+1)*PX},{line[c]*PX}")
    pts += [f"{W},{bottom*PX}", f"0,{bottom*PX}"]
    out.append(f'<polygon points="{" ".join(pts)}" fill="{fill}"/>')

# 5×7 pixel font for the wordmark.
FONT = {
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "N": ["10001", "11001", "11001", "10101", "10011", "10011", "10001"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
}
def word(text, c0, r0, fill, shadow=None):
    for sh in ([shadow] if shadow else []):  # drop shadow first
        cx = c0
        for ch in text:
            for r, row in enumerate(FONT[ch]):
                for k, bit in enumerate(row):
                    if bit == "1":
                        rect(cx + k + 1, r0 + r + 1, 1, 1, sh)
            cx += 6
    cx = c0
    for ch in text:
        for r, row in enumerate(FONT[ch]):
            for k, bit in enumerate(row):
                if bit == "1":
                    rect(cx + k, r0 + r, 1, 1, fill)
        cx += 6

# ── compose, back to front ──────────────────────────────────────────────────
rect(0, 0, COLS, ROWS, SKY[0][2])                       # base
for r0, r1, col in SKY:
    rect(0, r0, COLS, r1 - r0, col)                     # sky bands

# faint dawn stars in the dark upper bands
for _ in range(26):
    sc, sr = random.randint(0, COLS - 1), random.randint(0, 9)
    rect(sc, sr, 1, 1, "#cdd6f2", op=random.uniform(0.25, 0.6))

# distant range — jagged dawn peaks (drawn before the sun, which rises in front)
far = ridge_linear([(0, 29), (8, 22), (16, 26), (24, 16), (33, 27), (41, 20),
                    (50, 28), (60, 18), (72, 25), (84, 14), (96, 24), (106, 20),
                    (118, 27), (130, 16), (142, 25), (152, 21), (160, 29)])
mountain([y + 1 for y in far], MTN_SHADE)               # shadow offset
mountain(far, MTN)
for (p, t) in [(84, 14), (24, 16), (130, 16)]:          # clean sunrise-lit caps
    rect(p, t, 1, 1, SNOW); rect(p - 1, t + 1, 3, 1, SNOW)

# rising sun, in front of the range — its base is tucked behind the green hills
SCX, SCY, RR = 112, 23, 8
out.append(f'<circle cx="{SCX*PX}" cy="{SCY*PX}" r="{RR*PX*2.7}" fill="{GLOW}" opacity="0.10"/>')
out.append(f'<circle cx="{SCX*PX}" cy="{SCY*PX}" r="{RR*PX*1.7}" fill="{GLOW}" opacity="0.16"/>')
for c in range(SCX - RR, SCX + RR + 1):
    for r in range(SCY - RR, SCY + RR + 1):
        d = math.hypot(c - SCX, r - SCY)
        if d <= RR:
            rect(c, r, 1, 1, SUN_CORE if d <= RR - 3 else SUN_BODY)

# soft pixel clouds, clear of the wordmark
for (cc, cr) in [(50, 12), (140, 7)]:
    rect(cc + 1, cr - 1, 4, 1, "#ffeede", op=0.7)
    rect(cc, cr, 6, 1, "#f7dcc4", op=0.85)
    rect(cc + 1, cr + 1, 5, 1, "#e7b89c", op=0.6)

# a small flock drifting between the wordmark and the sun
for (bc, br) in [(60, 8), (67, 6), (74, 9), (82, 7), (89, 5)]:
    rect(bc, br + 1, 1, 1, BIRD); rect(bc + 1, br, 1, 1, BIRD)
    rect(bc + 2, br, 1, 1, BIRD); rect(bc + 3, br + 1, 1, 1, BIRD)

# rolling greenery, three layers for depth
mountain(ridge(34, [(46, 5, 30), (110, 6, 34)], 0.5), HILL_FAR)
mountain(ridge(38, [(20, 4, 26), (90, 5, 30), (150, 4, 24)], 0.5), HILL_MID)
mountain(ridge(41, [(60, 3, 40), (130, 4, 30)], 0.4), HILL_NEAR)
rect(0, 44, COLS, ROWS - 44, GROUND)                    # foreground floor

# a few pixel pines on the near ground
def pine(c, r):
    rect(c, r + 5, 1, 2, TRUNK)
    for i, wch in enumerate([1, 3, 5]):                 # tiers, widening down
        rect(c - wch // 2, r + i * 2, wch, 2, TREE)
        rect(c - wch // 2, r + i * 2, 1, 1, TREE_HI)
for (pc, pr) in [(24, 38), (33, 40), (140, 39), (150, 41), (128, 41)]:
    pine(pc, pr)

# wordmark + tagline
word("LUCENT", 9, 6, CREAM, shadow=INK)
out.append(
    f'<text x="{10*PX}" y="{15*PX+4}" fill="{CREAM}" opacity="0.9" '
    f'font-family="Menlo,Consolas,monospace" font-size="{int(PX*1.7)}" '
    f'letter-spacing="3">finances, illuminated.</text>')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
       f'width="{W}" height="{H}" shape-rendering="crispEdges" '
       f'role="img" aria-label="Lucent — finances, illuminated.">\n'
       + "\n".join(out) + "\n</svg>\n")

dst = os.path.join(os.path.dirname(__file__), "banner.svg")
with open(dst, "w") as f:
    f.write(svg)
print(f"wrote {dst}  ({len(svg)//1024} KB, {len(out)} elements)")
