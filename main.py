"""picture-tastes-one: a steaming bowl of ramen, drawn procedurally.

Pure Python standard library only (zlib + struct PNG encoder, no PIL, no
network, no randomness, no time). Two runs produce byte-identical PNGs.

Writes $MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png) and a
local copy entry.png next to this file.

Scene: a top-down bowl of tonkotsu-style ramen on a dark wooden table -
glossy orange broth, wavy noodles, chashu pork, a soft egg with a jammy
yolk, nori, spring onions, sesame, chopsticks on the rim, steam rising.
"""

import hashlib
import math
import os
import struct
import zlib
from pathlib import Path

SIZE = 1024
SS = 2                      # supersample factor: draw at 2048, downscale
W = SIZE * SS


def S(v):
    return int(round(v * SS))


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# ---------------------------------------------------------------- palette
TABLE_TOP = (74, 44, 26)
TABLE_BOT = (38, 21, 12)
PLANK = (30, 16, 8)
GLOW_IN = (122, 74, 40)
SHADOW1 = (28, 15, 7)
SHADOW2 = (20, 10, 4)
BOWL_OUT = (125, 26, 18)
BOWL_DARK = (96, 18, 12)
RIM = (178, 54, 28)
RIM_HI = (222, 106, 74)
BROTH_OUT = (176, 74, 18)
BROTH_IN = (242, 165, 66)
SWIRL = (247, 180, 92)
OIL = (240, 192, 90)
CHILI = (214, 60, 20)
NOODLE = (246, 217, 138)
NOODLE_SHADE = (217, 169, 79)
NOODLE_HI = (255, 233, 173)
CHASHU_OUT = (201, 106, 94)
CHASHU_IN = (232, 169, 143)
CHASHU_FAT = (246, 221, 208)
EGG_WHITE = (253, 246, 234)
EGG_SHADE = (238, 222, 196)
YOLK_OUT = (224, 127, 10)
YOLK_IN = (247, 183, 55)
NORI = (31, 45, 27)
NORI_HI = (46, 68, 38)
ONION_OUT = (47, 143, 62)
ONION_IN = (126, 208, 127)
STICK = (156, 107, 51)
STICK_HI = (192, 138, 74)
STICK_DARK = (110, 72, 32)
WHITE = (255, 255, 255)
CREAM_SEED = (255, 248, 224)
BLACK_SEED = (42, 26, 18)

# ------------------------------------------------------------------- buffer
buf = bytearray(W * W * 3)


def _off(x, y):
    return (y * W + x) * 3


def hline(x0, x1, y, color):
    """Solid horizontal run, inclusive, clipped."""
    if y < 0 or y >= W:
        return
    x0 = max(0, x0)
    x1 = min(W - 1, x1)
    if x1 < x0:
        return
    o = _off(x0, y)
    n = x1 - x0 + 1
    buf[o:o + 3 * n] = bytes(color) * n


def fill_circle(cx, cy, r, color):
    cx, cy, r = S(cx), S(cy), S(r)
    r2 = r * r
    for y in range(cy - r, cy + r + 1):
        dy = y - cy
        dx = int(math.sqrt(max(0, r2 - dy * dy)))
        hline(cx - dx, cx + dx, y, color)


def fill_ellipse(cx, cy, rx, ry, color):
    cx, cy, rx, ry = S(cx), S(cy), S(rx), S(ry)
    for y in range(cy - ry, cy + ry + 1):
        dy = (y - cy) / ry
        dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
        hline(cx - dx, cx + dx, y, color)


def fill_poly(pts, color):
    pts = [(S(x), S(y)) for x, y in pts]
    ys = [p[1] for p in pts]
    n = len(pts)
    for y in range(min(ys), max(ys) + 1):
        xs = []
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                t = (y - y1) / (y2 - y1)
                xs.append(int(x1 + t * (x2 - x1)))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            hline(xs[i], xs[i + 1], y, color)


def radial_disc(cx, cy, r, c_outer, c_inner, steps=28):
    """Smooth radial gradient disc via concentric circles."""
    for i in range(steps, 0, -1):
        t = i / steps
        fill_circle(cx, cy, r * t, lerp(c_outer, c_inner, 1.0 - t))


def arc_dots(cx, cy, r, a0, a1, color, dot_r, step_deg=5):
    a = a0
    while a <= a1:
        rad = math.radians(a)
        fill_circle(cx + r * math.cos(rad), cy + r * math.sin(rad),
                    dot_r, color)
        a += step_deg


def thick_arc(cx, cy, r, a0, a1, color, width):
    """Continuous arc band (overlapping dots so no beaded look)."""
    a = a0
    while a <= a1:
        rad = math.radians(a)
        fill_circle(cx + r * math.cos(rad), cy + r * math.sin(rad),
                    width / 2, color)
        a += 0.75


def blend_px(x, y, color, a):
    if 0 <= x < W and 0 <= y < W:
        o = _off(x, y)
        ia = 1.0 - a
        buf[o] = int(color[0] * a + buf[o] * ia)
        buf[o + 1] = int(color[1] * a + buf[o + 1] * ia)
        buf[o + 2] = int(color[2] * a + buf[o + 2] * ia)


def soft_ellipse(cx, cy, rx, ry, color, a_max):
    """Translucent ellipse with a soft falloff edge (steam, gloss)."""
    cx, cy, rx, ry = S(cx), S(cy), S(rx), S(ry)
    for y in range(cy - ry, cy + ry + 1):
        if y < 0 or y >= W:
            continue
        dy = (y - cy) / ry
        span = rx * math.sqrt(max(0.0, 1.0 - dy * dy))
        for x in range(int(cx - span), int(cx + span) + 1):
            if x < 0 or x >= W:
                continue
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d >= 1.0:
                continue
            a = a_max * (1.0 - d)
            a = a * a * (3.0 - 2.0 * a)
            blend_px(x, y, color, a)


def noodle(x0, y0, x1, y1, amp, freq, phase, width):
    """One wavy noodle strand: shade pass, body, highlight pass."""
    steps = 70
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t + amp * math.sin(phase + freq * t * 2 * math.pi)
        pts.append((x, y))
    for (x, y) in pts:
        fill_circle(x, y + 2.5, width, NOODLE_SHADE)
    for (x, y) in pts:
        fill_circle(x, y, width, NOODLE)
    for (x, y) in pts:
        fill_circle(x, y - 2.5, width * 0.35, NOODLE_HI)


def onion(x, y, r=11):
    fill_circle(x, y, r, ONION_OUT)
    fill_circle(x, y, r * 0.62, ONION_IN)
    fill_circle(x, y, r * 0.25, ONION_OUT)


def chashu(cx, cy, r):
    radial_disc(cx, cy, r, CHASHU_OUT, CHASHU_IN, steps=18)
    # marbled fat swirl
    arc_dots(cx, cy, r * 0.55, 20, 300, CHASHU_FAT, r * 0.13, step_deg=8)
    arc_dots(cx, cy, r * 0.28, 200, 480, CHASHU_FAT, r * 0.10, step_deg=10)
    # seared rim
    arc_dots(cx, cy, r * 0.92, 0, 360, (150, 70, 55), r * 0.06, step_deg=6)


# -------------------------------------------------------------------- scene
def draw():
    # table: vertical gradient + plank seams
    for y in range(W):
        t = y / (W - 1)
        hline(0, W - 1, y, lerp(TABLE_TOP, TABLE_BOT, t))
    for py in (180, 420, 760, 940):
        for y in range(S(py), S(py) + 3):
            hline(0, W - 1, y, PLANK)

    # soft shadow under the bowl
    fill_ellipse(512, 938, 350, 44, SHADOW1)
    fill_ellipse(512, 934, 300, 36, SHADOW2)

    # bowl: lacquered red exterior
    radial_disc(512, 580, 352, BOWL_OUT, BOWL_DARK, steps=22)
    # rim ring + highlight on the upper-left rim
    fill_circle(512, 580, 330, RIM)
    thick_arc(512, 580, 318, 150, 330, RIM_HI, 10)
    thick_arc(512, 580, 318, 170, 310, (240, 140, 100), 4)

    # broth
    radial_disc(512, 580, 302, BROTH_OUT, BROTH_IN, steps=26)
    # glossy swirl
    thick_arc(512, 580, 250, 200, 340, SWIRL, 12)
    thick_arc(512, 580, 190, 30, 150, SWIRL, 10)
    for (ox, oy, orad) in ((400, 430, 9), (660, 420, 7), (700, 700, 8),
                           (350, 700, 6), (590, 330, 6), (450, 770, 7)):
        fill_circle(ox, oy, orad, OIL)
        fill_circle(ox - orad * 0.3, oy - orad * 0.3, orad * 0.35, WHITE)
    for (ox, oy, orad) in ((430, 360, 6), (680, 620, 5), (330, 520, 5)):
        fill_circle(ox, oy, orad, CHILI)
        fill_circle(ox - orad * 0.3, oy - orad * 0.3, orad * 0.3, (255, 150, 110))

    # nori sheet standing at the back of the bowl
    fill_poly([(445, 330), (560, 325), (578, 452), (462, 458)], NORI)
    fill_poly([(460, 345), (548, 341), (560, 440), (474, 444)], NORI_HI)

    # noodles
    noodle(320, 520, 700, 500, 14, 2.2, 0.0, 10)
    noodle(330, 570, 710, 560, 18, 2.6, 1.1, 10)
    noodle(340, 620, 690, 630, 16, 2.0, 2.2, 10)
    noodle(350, 670, 680, 690, 14, 2.4, 0.6, 10)
    noodle(360, 720, 660, 730, 12, 2.8, 1.8, 10)
    noodle(380, 480, 640, 470, 12, 2.2, 2.9, 10)
    noodle(420, 740, 620, 760, 10, 3.0, 0.4, 10)
    noodle(300, 600, 500, 590, 20, 1.8, 1.5, 10)
    noodle(560, 700, 720, 680, 12, 2.2, 2.5, 10)
    noodle(480, 540, 700, 520, 10, 2.6, 0.9, 10)
    noodle(330, 450, 660, 440, 13, 2.4, 0.8, 10)
    noodle(380, 420, 620, 430, 11, 2.6, 2.0, 10)
    noodle(560, 480, 730, 500, 12, 2.2, 1.2, 10)
    noodle(300, 660, 560, 680, 14, 2.4, 1.6, 10)
    noodle(480, 760, 700, 750, 11, 2.6, 0.2, 10)

    # chashu pork, two overlapping slices
    chashu(330, 665, 78)
    chashu(385, 555, 92)

    # soft egg with jammy yolk
    fill_ellipse(625, 495, 96, 79, EGG_WHITE)
    fill_ellipse(625, 492, 88, 71, EGG_SHADE)
    fill_ellipse(625, 495, 84, 67, EGG_WHITE)
    radial_disc(625, 500, 50, YOLK_OUT, YOLK_IN, steps=16)
    soft_ellipse(608, 478, 18, 11, WHITE, 0.55)

    # spring onions
    for (ox, oy, orad) in ((450, 545, 11), (520, 600, 10), (600, 640, 11),
                           (380, 600, 9), (660, 580, 10), (480, 700, 11),
                           (560, 720, 10), (420, 660, 9), (640, 740, 10),
                           (560, 480, 9), (700, 640, 9), (340, 640, 9)):
        onion(ox, oy, orad)

    # sesame seeds, deterministic scatter via a tiny LCG (ports 1:1 to JS)
    state = 1234

    def _lcg(s):
        s = (s * 1103515245 + 12345) % 2147483648
        return s, s / 2147483648

    for _ in range(46):
        state, u1 = _lcg(state)
        state, u2 = _lcg(state)
        state, u3 = _lcg(state)
        ang = u1 * 2 * math.pi
        rad = 40 + u2 * 235
        sx = 512 + rad * math.cos(ang)
        sy = 580 + rad * math.sin(ang) * 0.92
        col = CREAM_SEED if u3 < 0.6 else BLACK_SEED
        fill_ellipse(sx, sy, 4.5, 2.5, col)

    # chopsticks resting on the rim, top right
    fill_poly([(660, 300), (985, 415), (988, 428), (663, 313)], STICK)
    fill_poly([(660, 300), (985, 415), (986, 419), (661, 304)], STICK_HI)
    fill_poly([(672, 322), (997, 437), (1000, 450), (675, 335)], STICK)
    fill_poly([(672, 322), (997, 437), (998, 441), (673, 326)], STICK_HI)
    fill_poly([(660, 300), (663, 313), (675, 335), (672, 322)], STICK_DARK)

    # steam rising above the bowl
    for base_x, phase in ((430, 0.0), (512, 1.4), (600, 2.6)):
        for k in range(5):
            y = 320 - k * 42
            x = base_x + 16 * math.sin(phase + k * 0.9)
            soft_ellipse(x, y, 64, 66, WHITE, 0.20)


def downscale():
    out = bytearray(SIZE * SIZE * 3)
    src = buf
    for oy in range(SIZE):
        y0 = oy * SS
        orow = oy * SIZE * 3
        for ox in range(SIZE):
            x0 = ox * SS
            o = orow + ox * 3
            s00 = (y0 * W + x0) * 3
            s01 = s00 + 3
            s10 = s00 + W * 3
            s11 = s10 + 3
            out[o] = (src[s00] + src[s01] + src[s10] + src[s11]) // 4
            out[o + 1] = (src[s00 + 1] + src[s01 + 1] + src[s10 + 1] + src[s11 + 1]) // 4
            out[o + 2] = (src[s00 + 2] + src[s01 + 2] + src[s10 + 2] + src[s11 + 2]) // 4
    return bytes(out)


def png_bytes(rgb):
    raw = bytearray()
    stride = SIZE * 3
    for y in range(SIZE):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def _write_retry(path, data, tries=25):
    """VM quirk: file writes often fail EPERM transiently; retry."""
    import time
    last = None
    for _ in range(tries):
        try:
            path.write_bytes(data)
            return True
        except OSError as e:
            last = e
            time.sleep(0.2)
    print(f"cannot write {path}: {last}")
    return False


def main():
    import sys
    png_stdout = "--png-stdout" in sys.argv
    draw()
    data = png_bytes(downscale())
    if png_stdout:
        # stdout must carry pure PNG bytes; diagnostics would corrupt it,
        # and python writes to regular files (incl. redirected stderr)
        # hit EPERM on this VM, so stay silent here.
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        return
    print(f"png bytes: {len(data)}")
    print(f"sha256: {hashlib.sha256(data).hexdigest()}")
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    targets = [Path(__file__).resolve().parent / "entry.png"]
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        targets.append(out_dir / "entry.png")
    except OSError as e:
        print(f"cannot use {out_dir}: {e}")
    for p in targets:
        if _write_retry(p, data):
            print(f"wrote {p}")


if __name__ == "__main__":
    main()
