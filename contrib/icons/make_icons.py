"""Original, generic profile pictures for the project's news bots (128 px WebP, no
metadata): ``python make_icons.py`` writes ``<bot>.webp`` and ``<bot>.alt`` here.
They are not the sources' logos on purpose: the UN emblem, CISA's seal and the NGOs'
and sites' logos may not be used this way, so each bot gets a plain symbol instead.
Drawn at 4x and scaled down for smooth edges. None of them imitates an
organisation's logo or emblem: plain symbols on plain colours."""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = 512
OUT = Path(__file__).parent
W = (255, 255, 255)
# any bold sans font; the letters on the newspaper icons only
FONT = next((f for f in ("/usr/share/fonts/google-noto-vf/NotoSans[wght].ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf")
             if not f.startswith("/") or Path(f).exists()), "DejaVuSans-Bold.ttf")


def canvas(bg):
    im = Image.new("RGB", (S, S), bg)
    return im, ImageDraw.Draw(im)


def globe(d, cx=256, cy=256, r=150, w=14, col=W):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=w)
    d.ellipse((cx - r * 0.45, cy - r, cx + r * 0.45, cy + r), outline=col, width=w)
    d.line((cx, cy - r, cx, cy + r), fill=col, width=w)
    d.line((cx - r, cy, cx + r, cy), fill=col, width=w)
    y = r * 0.55
    half = math.sqrt(r * r - y * y)
    d.line((cx - half, cy - y, cx + half, cy - y), fill=col, width=w)
    d.line((cx - half, cy + y, cx + half, cy + y), fill=col, width=w)


def badge(d, symbol, col):
    cx, cy, r = 390, 390, 100
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=W)
    symbol(d, cx, cy, col)


def leaf(d, cx, cy, col, s=1.0, vein=W):
    w = 46 * s
    body = [(cx, cy - 68 * s)]
    for t in range(0, 181, 10):
        body.append((cx + w * math.sin(math.radians(t)), cy - 68 * s + 136 * s * t / 180))
    for t in range(180, -1, -10):
        body.append((cx - w * math.sin(math.radians(t)), cy - 68 * s + 136 * s * t / 180))
    d.polygon(body, fill=col)
    d.line((cx, cy - 50 * s, cx, cy + 80 * s), fill=vein, width=max(2, int(8 * s)))


def scales(d, cx, cy, col):
    d.line((cx, cy - 60, cx, cy + 55), fill=col, width=10)
    d.line((cx - 60, cy - 40, cx + 60, cy - 40), fill=col, width=10)
    d.rectangle((cx - 35, cy + 50, cx + 35, cy + 62), fill=col)
    for x in (cx - 60, cx + 60):
        d.line((x, cy - 40, x - 22, cy + 5), fill=col, width=6)
        d.line((x, cy - 40, x + 22, cy + 5), fill=col, width=6)
        d.pieslice((x - 28, cy - 22, x + 28, cy + 26), 0, 180, fill=col)


def parcel(d, cx, cy, col):
    d.rectangle((cx - 55, cy - 40, cx + 55, cy + 50), fill=col)
    d.rectangle((cx - 62, cy - 58, cx + 62, cy - 36), fill=col)
    d.rectangle((cx - 8, cy - 58, cx + 8, cy + 50), fill=W)


def pulse(d, cx, cy, col):
    pts = [(cx - 70, cy), (cx - 30, cy), (cx - 15, cy - 45), (cx + 5, cy + 50),
           (cx + 20, cy - 15), (cx + 32, cy), (cx + 70, cy)]
    d.line(pts, fill=col, width=12, joint="curve")


def megaphone(d, cx, cy, col, s=1.0):
    d.polygon([(cx - 90 * s, cy - 30 * s), (cx + 40 * s, cy - 95 * s), (cx + 40 * s, cy + 95 * s),
               (cx - 90 * s, cy + 30 * s)], fill=col)
    d.rectangle((cx - 120 * s, cy - 30 * s, cx - 85 * s, cy + 30 * s), fill=col)
    d.rectangle((cx - 85 * s, cy + 25 * s, cx - 55 * s, cy + 100 * s), fill=col)
    for r in (70, 110):
        d.arc((cx + 40 * s - r * s, cy - r * s, cx + 40 * s + r * s, cy + r * s), -35, 35,
              fill=col, width=int(14 * s))


def magnifier(d, cx, cy, col, s=1.0):
    r = 95 * s
    d.ellipse((cx - r - 30 * s, cy - r - 30 * s, cx + r - 30 * s, cy + r - 30 * s), outline=col,
              width=int(28 * s))
    d.line((cx + 45 * s, cy + 45 * s, cx + 135 * s, cy + 135 * s), fill=col, width=int(44 * s))


def shield(d, cx, cy, col, inner):
    d.polygon([(cx, cy - 175), (cx + 145, cy - 120), (cx + 130, cy + 40),
               (cx, cy + 180), (cx - 130, cy + 40), (cx - 145, cy - 120)], fill=col)
    inner(d, cx, cy)


def check(d, cx, cy):
    d.line([(cx - 65, cy), (cx - 15, cy + 50), (cx + 75, cy - 55)], fill=W, width=34, joint="curve")


def warning(d, cx, cy):
    d.polygon([(cx, cy - 95), (cx + 100, cy + 75), (cx - 100, cy + 75)], fill=(250, 200, 40))
    d.rectangle((cx - 11, cy - 40, cx + 11, cy + 25), fill=(40, 40, 40))
    d.ellipse((cx - 13, cy + 37, cx + 13, cy + 63), fill=(40, 40, 40))


def bars(d, cx, cy, col):
    for i, h in enumerate((110, 190, 150, 260)):
        x = cx - 165 + i * 90
        d.rectangle((x, cy + 140 - h, x + 60, cy + 140), fill=col)
    d.line((cx - 190, cy + 150, cx + 190, cy + 150), fill=col, width=14)


def newspaper(d, letter, accent):
    d.rounded_rectangle((110, 120, 402, 400), radius=24, fill=W)
    d.rectangle((140, 150, 372, 215), fill=accent)
    for y in (240, 275, 310, 345):
        d.rectangle((140, y, 250, y + 14), fill=(150, 150, 150))
        d.rectangle((268, y, 372, y + 14), fill=(150, 150, 150))
    font = ImageFont.truetype(FONT, 54 if len(letter) < 3 else 44)
    d.text((256, 183), letter, fill=W, font=font, anchor="mm")


def save(name, im, alt):
    OUT.mkdir(exist_ok=True)
    im.resize((128, 128), Image.LANCZOS).save(OUT / f"{name}.webp", "WEBP", quality=90, method=6)
    (OUT / f"{name}.alt").write_text(alt)


UN_BLUE = (56, 120, 190)


def un(name, sym, alt):
    im, d = canvas(UN_BLUE)
    if sym:
        globe(d, 220, 220, 150)
        badge(d, sym, UN_BLUE)
    else:
        globe(d, 256, 256, 175)
    save(name, im, alt)


un("un", None, "A white line drawing of a globe on blue")
un("un-climate", lambda d, x, y, c: leaf(d, x, y, (60, 140, 70), 0.9),
   "A white globe on blue, with a green leaf in a round badge")
un("un-humanrights", scales, "A white globe on blue, with balance scales in a round badge")
un("un-humanitarian", parcel, "A white globe on blue, with a tied parcel in a round badge")
un("un-health", pulse, "A white globe on blue, with a heartbeat line in a round badge")

im, d = canvas((90, 70, 140)); megaphone(d, 256, 256, W, 1.3)
save("amnesty", im, "A white megaphone on purple")
im, d = canvas((40, 100, 110)); magnifier(d, 256, 256, W, 1.15)
save("hrw", im, "A white magnifying glass on teal")
im, d = canvas((60, 140, 70)); leaf(d, 256, 256, W, 2.4, vein=(60, 140, 70))
save("mongabay", im, "A white leaf on green")
im, d = canvas((30, 45, 80)); shield(d, 256, 256, (80, 150, 220), check)
save("cisa", im, "A blue shield with a white check mark on dark blue")
im, d = canvas((30, 45, 80)); shield(d, 256, 256, (80, 150, 220), warning)
save("kev", im, "A blue shield with a yellow warning triangle on dark blue")
im, d = canvas((245, 245, 240)); bars(d, 256, 220, (70, 110, 160))
save("owid", im, "A blue bar chart on off-white")
for name, letter, bg, accent in (("hackernews", "HN", (70, 70, 70), (120, 120, 120)),
                                 ("lobsters", "L", (110, 60, 60), (160, 90, 90)),
                                 ("arstechnica", "A", (60, 70, 90), (100, 115, 140)),
                                 ("theregister", "R", (80, 80, 60), (130, 130, 95)),
                                 ("lwn", "LWN", (60, 80, 70), (95, 125, 110)),
                                 ("propublica", "P", (70, 70, 100), (110, 110, 150)),
                                 ("restofworld", "W", (90, 70, 60), (140, 110, 95))):
    im, d = canvas(bg); newspaper(d, letter, accent)
    save(name, im, f"A plain newspaper page with the letters {letter} in its masthead")
def bubble(d):
    d.rounded_rectangle((90, 110, 422, 330), radius=60, fill=W)
    d.polygon([(170, 320), (150, 410), (250, 325)], fill=W)
    for x in (180, 256, 332):
        d.ellipse((x - 22, 198, x + 22, 242), fill=(70, 70, 70))


def book(d, col):
    d.polygon([(256, 160), (100, 120), (100, 380), (256, 420)], fill=W)
    d.polygon([(256, 160), (412, 120), (412, 380), (256, 420)], fill=(235, 235, 235))
    d.line((256, 160, 256, 420), fill=col, width=10)
    for y in (180, 220, 260, 300):
        d.line((130, y, 230, y + 24), fill=(170, 170, 170), width=8)
        d.line((282, y + 24, 382, y), fill=(170, 170, 170), width=8)


def padlock(d):
    d.arc((166, 90, 346, 290), 180, 360, fill=W, width=34)
    d.line((183, 190, 183, 250), fill=W, width=34)
    d.line((329, 190, 329, 250), fill=W, width=34)
    d.rounded_rectangle((130, 230, 382, 430), radius=26, fill=W)
    d.ellipse((236, 300, 276, 340), fill=(110, 40, 40))
    d.rectangle((248, 320, 264, 380), fill=(110, 40, 40))


def network(d):
    pts = [(256, 130), (140, 230), (372, 230), (190, 380), (322, 380), (256, 260)]
    for a in pts:
        for b in pts:
            if a < b and abs(a[0] - b[0]) + abs(a[1] - b[1]) < 260:
                d.line((a, b), fill=W, width=10)
    for x, y in pts:
        d.ellipse((x - 30, y - 30, x + 30, y + 30), fill=W)


im, d = canvas((60, 90, 130)); bubble(d)
save("xkcd", im, "A white speech bubble with three dots on blue")
im, d = canvas((150, 80, 60)); book(d, (150, 80, 60))
save("peppercarrot", im, "An open book on warm red")
im, d = canvas((110, 40, 40)); padlock(d)
save("arxiv-cr", im, "A white padlock on dark red")
im, d = canvas((40, 60, 90)); network(d)
save("arxiv-ai", im, "White dots joined by lines, like a small network, on dark blue")
im, d = canvas((50, 70, 110)); newspaper(d, "F", (90, 110, 160))
save("fedoramagazine", im, "A plain newspaper page with the letter F in its masthead")
print(sorted(p.name for p in OUT.glob("*.webp")))
