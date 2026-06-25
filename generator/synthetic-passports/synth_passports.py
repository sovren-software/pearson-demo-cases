#!/usr/bin/env python3
"""Synthetic passport dataset generator — for testing LEI's document-intake,
OCR/extraction, field-mapping, and review flows WITHOUT real personal documents.

Everything produced here is clearly-marked synthetic test data:
  * a red "SYNTHETIC SPECIMEN — NOT A REAL PASSPORT" banner across every page,
  * a diagonal SPECIMEN watermark, a placeholder silhouette photo (never a real face),
  * deliberately *stylized* (non-official) national emblems on a generic ICAO-9303
    TD3 data-page layout — it does not replicate any country's official design,
  * fictional names/numbers/dates, and a `synthetic: true` + disclaimer in every
    JSON sidecar.

The visible fields and the bottom MRZ are nonetheless realistic enough to exercise a
real extractor: the MRZ carries valid ICAO-9303 TD3 check digits (same algorithm the
Pearson corpus and LEI's `classify_passport_mrz` use), so a clean doc passes and the
`mrz_checkdigit_corrupt` variant trips the review gate.

Usage:
  python3 synth_passports.py list-countries
  python3 synth_passports.py sample                       # curated deterministic set
  python3 synth_passports.py generate --countries all --per-country 5 --seed 7 \
        --quality mix --defects mix --out out
  python3 synth_passports.py validate out                 # re-check MRZ + sidecars

Requires: Pillow (with raqm for Devanagari/Urdu shaping), numpy, and the Noto +
DejaVu fonts. No network, no external services.
"""
import argparse
import datetime as dt
import functools
import hashlib
import json
import math
import os
import random
import subprocess
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

try:
    import numpy as np
except Exception:  # numpy only needed for the 'noise' quality variant
    np = None

from countries import COUNTRIES, ORDER

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "out")

# Reproducible "today" so expired / near-expiry are well-defined and deterministic.
DEFAULT_AS_OF = dt.date(2026, 6, 25)

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

QUALITY_VARIANTS = ["clean", "blur", "noise", "low_res", "rotate", "skew",
                    "jpeg", "grayscale", "glare", "dark", "low_contrast"]
DEFECT_VARIANTS = ["none", "expired", "near_expiry", "mrz_checkdigit_corrupt",
                   "mrz_visible_mismatch", "missing_field", "date_format_variant"]

# ── fonts ────────────────────────────────────────────────────────────────────
FONT_QUERY = {
    "sans": "DejaVu Sans",
    "sansb": "DejaVu Sans:bold",
    "mono": "DejaVu Sans Mono",
    "deva": "Noto Sans Devanagari",
    "cjk_sc": "Noto Sans CJK SC",
    "cjk_kr": "Noto Sans CJK KR",
    "cjk_tc": "Noto Sans CJK TC",
    "arabic": "Noto Naskh Arabic",
}


@functools.lru_cache(maxsize=64)
def _font_file(query: str):
    """Resolve a fontconfig family query to (path, face_index)."""
    out = subprocess.check_output(
        ["fc-match", "-f", "%{file}\t%{index}", query], text=True).strip()
    path, _, index = out.partition("\t")
    return path, int(index or 0)


@functools.lru_cache(maxsize=256)
def font(key: str, size: int) -> ImageFont.FreeTypeFont:
    path, index = _font_file(FONT_QUERY[key])
    return ImageFont.truetype(path, size, index=index, layout_engine=ImageFont.Layout.RAQM)


# ── ICAO 9303 TD3 MRZ (same algorithm as generator/generate_cases.py:build_mrz) ──
def check_digit(s: str) -> str:
    w = [7, 3, 1]
    t = 0
    for i, c in enumerate(s):
        v = 0 if c == "<" else (int(c) if c.isdigit() else ord(c) - 55)
        t += v * w[i % 3]
    return str(t % 10)


def mrz_name_field(surname: str, given: str) -> str:
    s = surname.upper().replace("-", "<").replace(" ", "<")
    g = given.upper().replace("-", "<").replace(" ", "<")
    return (f"{s}<<{g}" + "<" * 39)[:39]


def build_mrz(p: dict):
    """Return (line1, line2) for a TD3 passport. Both lines are exactly 44 chars."""
    country = p["nationality"]
    line1 = f"P<{country}{mrz_name_field(p['surname'], p['given'])}"
    assert len(line1) == 44, (len(line1), line1)
    passport = (p["passport_number"].upper() + "<" * 9)[:9]
    pcd = check_digit(passport)
    dob = p["dob"].replace("-", "")[2:]
    dcd = check_digit(dob)
    exp = p["passport_expiration"].replace("-", "")[2:]
    ecd = check_digit(exp)
    personal = "<" * 14
    pncd = check_digit(personal)
    composite = passport + pcd + dob + dcd + exp + ecd + personal + pncd
    ccd = check_digit(composite)
    line2 = f"{passport}{pcd}{country}{dob}{dcd}{p['sex']}{exp}{ecd}{personal}{pncd}{ccd}"
    assert len(line2) == 44, (len(line2), line2)
    return line1, line2


def mrz_checkdigits_valid(line2: str) -> bool:
    """Verify the composite check digit of a TD3 second line (what LEI gates on)."""
    if len(line2) != 44:
        return False
    composite = line2[0:10] + line2[13:20] + line2[21:43]
    return check_digit(composite) == line2[43]


# ── dates ────────────────────────────────────────────────────────────────────
def iso(d: dt.date) -> str:
    return d.isoformat()


def add_years(d: dt.date, years: int) -> dt.date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # Feb 29
        return d.replace(year=d.year + years, day=28)


def fmt_date(iso_s: str, style: str = "dmy_mon") -> str:
    y, m, day = (int(x) for x in iso_s.split("-"))
    if style == "dmy_mon":
        return f"{day:02d} {MONTHS[m - 1]} {y}"
    if style == "dmy_slash":
        return f"{day:02d}/{m:02d}/{y}"
    if style == "iso":
        return f"{y:04d}-{m:02d}-{day:02d}"
    if style == "dmy_dot":
        return f"{day:02d}.{m:02d}.{y}"
    return f"{day:02d} {MONTHS[m - 1]} {y}"


# ── synthetic person ─────────────────────────────────────────────────────────
def gen_pn(fmt: str, rng: random.Random) -> str:
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"          # no I/O/Q
    alnum = letters + "0123456789"
    out = []
    for ch in fmt:
        if ch == "#":
            out.append(rng.choice("0123456789"))
        elif ch == "A":
            out.append(rng.choice(letters))
        elif ch == "N":
            out.append(rng.choice(alnum))
        else:
            out.append(ch)
    return "".join(out)


def synth_person(code: str, rng: random.Random, as_of: dt.date) -> dict:
    c = COUNTRIES[code]
    sex = rng.choice(["M", "F"])
    given_pool = c["given_m"] if sex == "M" else c["given_f"]
    given = rng.choice(given_pool)
    surname = rng.choice(c["surnames"])

    age = rng.randint(24, 55)
    dob = add_years(as_of, -age) - dt.timedelta(days=rng.randint(0, 364))
    issue = as_of - dt.timedelta(days=rng.randint(60, 8 * 365))
    expiry = add_years(issue, 10)

    return {
        "country": code,
        "nationality": code,
        "nationality_long": c["nationality_long"],
        "surname": surname,
        "given": given,
        "sex": sex,
        "dob": iso(dob),
        "place_of_birth": rng.choice(c["places"]),
        "passport_number": gen_pn(c["pn_format"], rng),
        "passport_issue": iso(issue),
        "passport_expiration": iso(expiry),
        "authority": c["authority"],
    }


def apply_defect(p: dict, defect: str, rng: random.Random, as_of: dt.date):
    """Mutate `p` for a format/defect variation. Returns a render-instruction dict:
      {visible: {field: shown_value}, blank: [fields], mrz_corrupt: bool,
       date_style: str, expected_flags: [...], applied: str}
    'visible' overrides what is PRINTED (used to diverge print from ground truth)."""
    inst = {"visible": {}, "blank": [], "mrz_corrupt": False,
            "date_style": "dmy_mon", "expected_flags": [], "applied": defect}

    if defect == "expired":
        issue = as_of - dt.timedelta(days=rng.randint(10 * 365, 14 * 365))
        p["passport_issue"] = iso(issue)
        p["passport_expiration"] = iso(add_years(issue, 10))
        inst["expected_flags"] = ["passport_expired"]

    elif defect == "near_expiry":
        expiry = as_of + dt.timedelta(days=rng.randint(10, 150))
        p["passport_expiration"] = iso(expiry)
        p["passport_issue"] = iso(add_years(expiry, -10))
        inst["expected_flags"] = ["passport_near_expiry"]

    elif defect == "mrz_checkdigit_corrupt":
        inst["mrz_corrupt"] = True
        inst["expected_flags"] = ["mrz_checkdigit_invalid"]

    elif defect == "mrz_visible_mismatch":
        # The printed passport number differs from the (valid) one encoded in the MRZ.
        real = p["passport_number"]
        shown = list(real)
        pos = next((i for i, ch in enumerate(shown) if ch.isdigit()), len(shown) - 1)
        shown[pos] = str((int(shown[pos]) + 5) % 10) if shown[pos].isdigit() else "8"
        inst["visible"]["passport_number"] = "".join(shown)
        inst["expected_flags"] = ["mrz_visible_field_mismatch"]

    elif defect == "missing_field":
        field = rng.choice(["place_of_birth", "passport_issue", "authority"])
        inst["blank"] = [field]
        inst["expected_flags"] = [f"missing_{field}"]

    elif defect == "date_format_variant":
        inst["date_style"] = rng.choice(["dmy_slash", "iso", "dmy_dot"])
        # not a defect — a parsing-robustness variation; no expected flag

    return inst


# ── stylized (NON-OFFICIAL) emblems ──────────────────────────────────────────
def _star(cx, cy, ro):
    ri = ro * 0.42
    pts = []
    for i in range(10):
        ang = math.radians(-90 + i * 36)
        rr = ro if i % 2 == 0 else ri
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return pts


def draw_emblem(d: ImageDraw.ImageDraw, kind: str, color, cx, cy, r, S):
    """All emblems are deliberate geometric approximations, not official arms."""
    cx, cy, r = S(cx), S(cy), S(r)
    lw = max(2, S(2))
    if kind == "chakra":  # India: wheel + spokes
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=lw)
        for k in range(24):
            a = math.radians(k * 15)
            d.line([cx, cy, cx + (r - 2) * math.cos(a), cy + (r - 2) * math.sin(a)],
                   fill=color, width=max(1, S(1)))
        d.ellipse([cx - S(4), cy - S(4), cx + S(4), cy + S(4)], fill=color)
    elif kind == "stars":  # China: one large + four small
        d.polygon(_star(cx - S(6), cy, r * 0.6), fill=color)
        for dx, dy in [(14, -14), (22, -2), (22, 12), (14, 22)]:
            d.polygon(_star(cx + S(dx), cy + S(dy), r * 0.22), fill=color)
    elif kind == "sunburst":  # Taiwan: 12-ray sun
        for k in range(12):
            a = math.radians(k * 30)
            d.line([cx, cy, cx + r * math.cos(a), cy + r * math.sin(a)], fill=color, width=S(3))
        d.ellipse([cx - S(7), cy - S(7), cx + S(7), cy + S(7)], fill=color)
    elif kind == "sun":  # Philippines: rays + face circle
        for k in range(8):
            a = math.radians(k * 45)
            d.line([cx + r * 0.5 * math.cos(a), cy + r * 0.5 * math.sin(a),
                    cx + r * math.cos(a), cy + r * math.sin(a)], fill=color, width=S(3))
        d.ellipse([cx - S(r // S(1) if False else 0) - S(10), cy - S(10),
                   cx + S(10), cy + S(10)], outline=color, width=lw)
    elif kind == "maple":  # Canada: stylized leaf (simple)
        pts = [(0, -r), (r * 0.25, -r * 0.3), (r * 0.7, -r * 0.45), (r * 0.4, -r * 0.05),
               (r * 0.8, r * 0.2), (r * 0.25, r * 0.18), (r * 0.35, r * 0.8),
               (0, r * 0.5),
               (-r * 0.35, r * 0.8), (-r * 0.25, r * 0.18), (-r * 0.8, r * 0.2),
               (-r * 0.4, -r * 0.05), (-r * 0.7, -r * 0.45), (-r * 0.25, -r * 0.3)]
        d.polygon([(cx + x, cy + y) for x, y in pts], fill=color)
    elif kind == "taegeuk":  # Korea: two-tone yin-yang circle
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=lw)
        d.pieslice([cx - r, cy - r, cx + r, cy + r], 90, 270, fill=color)
        d.ellipse([cx - r, cy - r // 2 - r // 2, cx, cy], fill="#ffffff")
        d.ellipse([cx, cy, cx + r, cy + r], fill="#ffffff")
        d.ellipse([cx - r, cy - r, cx, cy], fill=color)
    elif kind == "seal":  # Mexico: concentric rings
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=S(3))
        d.ellipse([cx - (r - 7), cy - (r - 7), cx + (r - 7), cy + (r - 7)],
                  outline="#006847", width=lw)
        d.ellipse([cx - S(4), cy - S(4), cx + S(4), cy + S(4)], fill=color)
    elif kind == "globe":  # Brazil: globe with band
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=lw)
        d.line([cx - r, cy, cx + r, cy], fill=color, width=max(1, S(1)))
        d.arc([cx - r, cy - r, cx + r, cy + r], 200, 340, fill=color, width=S(3))
    elif kind == "shield":  # UK: simple shield outline
        pts = [(-r * 0.7, -r), (r * 0.7, -r), (r * 0.7, r * 0.2),
               (0, r), (-r * 0.7, r * 0.2)]
        d.polygon([(cx + x, cy + y) for x, y in pts], outline=color, width=lw)
        d.line([cx, cy - r, cx, cy + r * 0.6], fill=color, width=max(1, S(1)))
        d.line([cx - r * 0.6, cy - r * 0.35, cx + r * 0.6, cy - r * 0.35],
               fill=color, width=max(1, S(1)))
    elif kind == "crescent":  # Pakistan: crescent + star
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
        d.ellipse([cx - r + S(7), cy - r, cx + r + S(7), cy + r], fill=None,
                  outline=None)
        # carve the crescent by overpainting an offset circle in the header color later;
        # simpler: draw crescent as two arcs
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=None, outline=color, width=S(3))
        d.polygon(_star(cx + S(8), cy, r * 0.4), fill=color)


# ── rendering ────────────────────────────────────────────────────────────────
def _find_coeffs(src, dst):
    matrix = []
    for s, d in zip(dst, src):
        matrix.append([d[0], d[1], 1, 0, 0, 0, -s[0] * d[0], -s[0] * d[1]])
        matrix.append([0, 0, 0, d[0], d[1], 1, -s[1] * d[0], -s[1] * d[1]])
    A = np.array(matrix, dtype=float)
    B = np.array(src, dtype=float).reshape(8)
    res = np.linalg.solve(A, B)
    return list(res)


def render_passport(p: dict, mrz, inst: dict, width: int = 1000) -> Image.Image:
    """Render the data page at `width` px (height = width*0.64). Returns RGB image."""
    c = COUNTRIES[p["country"]]
    SS = 2                                  # supersample for crisp text
    iscale = (width / 1000.0) * SS

    def S(v):
        return int(round(v * iscale))

    W, H = S(1000), S(640)
    img = Image.new("RGB", (W, H), c["tint"])
    d = ImageDraw.Draw(img)

    def text(xy, s, key, size, fill, anchor="la", direction="ltr"):
        d.text((S(xy[0]), S(xy[1])), s, font=font(key, S(size)), fill=fill,
               anchor=anchor, direction=direction)

    HEADER, COUNTRY_C, ACCENT = c["header"], c["country_color"], c["accent"]
    LB, VB = "#5b6b78", "#10222f"           # label-grey / value-dark

    # header band + stylized emblem
    d.rectangle([0, 0, W, S(100)], fill=HEADER)
    draw_emblem(d, c["emblem"], c["emblem_color"], 58, 50, 30, S)
    # native + english country name (RTL handled for Urdu)
    if c["native_dir"] == "rtl":
        text((470, 26), c["native"], c["native_font"], 22, COUNTRY_C, anchor="ra", direction="rtl")
    else:
        text((108, 24), c["native"], c["native_font"], 22, COUNTRY_C)
    text((108, 62), c["country_en"], "sans", 12, "#dfe6f0")
    # passport word (native + english), right side
    if c["native_dir"] == "rtl":
        text((958, 22), c["passport_native"], c["passport_font"], 20, COUNTRY_C, anchor="ra", direction="rtl")
    else:
        text((760, 22), c["passport_native"], c["passport_font"], 20, COUNTRY_C)
    text((760, 60), "PASSPORT", "sans", 12, "#dfe6f0")
    text((905, 80), "SPECIMEN", "sansb", 10, ACCENT)

    # ── red SAFETY sub-banner (prominent, but thin so fields stay clear) ──
    d.rectangle([0, S(100), W, S(124)], fill="#fdecec")
    text((500, 112), "SYNTHETIC SPECIMEN  ·  FICTITIOUS TEST DATA  ·  NOT A REAL "
         "PASSPORT  ·  NOT VALID FOR TRAVEL OR IDENTITY", "sansb", 10.5, "#b00020",
         anchor="mm")

    # photo placeholder (silhouette — never a real face)
    px0, py0, px1, py1 = 40, 150, 250, 392
    d.rectangle([S(px0), S(py0), S(px1), S(py1)], fill="#d9e0e6", outline="#9fb0bc", width=S(1))
    hcx, hcy = (px0 + px1) / 2, py0 + 78
    d.ellipse([S(hcx - 34), S(hcy - 34), S(hcx + 34), S(hcy + 34)], fill="#b6c2cc")
    d.pieslice([S(hcx - 62), S(hcy + 26), S(hcx + 62), S(hcy + 150)], 180, 360, fill="#b6c2cc")
    text(((px0 + px1) / 2, py1 - 22), "SPECIMEN PHOTO", "sans", 11, "#62727f", anchor="ma")

    # field values, honoring print-overrides + blanked fields + date style
    vis = inst.get("visible", {})
    blank = set(inst.get("blank", []))
    style = inst.get("date_style", "dmy_mon")

    def val(field, raw):
        if field in blank:
            return ""
        return vis.get(field, raw)

    pn_shown = val("passport_number", p["passport_number"]).upper()
    text((640, 150), "Passport No.", "sans", 12, LB)
    text((640, 172), pn_shown, "sansb", 22, "#9b1b1b")
    text((885, 150), "Type", "sans", 12, LB)
    text((885, 172), "P", "sansb", 22, VB)

    rows_left = [
        ("Surname", "surname", p["surname"].upper(), 20),
        ("Given names", "given", p["given"].upper(), 20),
        ("Nationality", "nationality", f"{p['nationality_long'].upper()} / {p['nationality']}", 17),
        ("Date of birth", "dob", fmt_date(p["dob"], style), 18),
        ("Date of expiry", "passport_expiration", fmt_date(p["passport_expiration"], style), 18),
    ]
    ly = [150, 210, 270, 330, 392]
    for (label, fld, raw, sz), y in zip(rows_left, ly):
        text((300, y), label, "sans", 12, LB)
        text((300, y + 24), val(fld, raw), "sansb", sz, VB)

    # right column — single column at x=640 so wide date values never collide
    rows_right = [
        ("Sex", "sex", p["sex"], 18),
        ("Place of birth", "place_of_birth", p["place_of_birth"].upper(), 16),
        ("Date of issue", "passport_issue", fmt_date(p["passport_issue"], style), 18),
        ("Authority", "authority", c["authority"], 12),
    ]
    for (label, fld, raw, sz), y in zip(rows_right, [210, 270, 330, 392]):
        text((640, y), label, "sans", 12, LB)
        text((640, y + 24), val(fld, raw), "sansb" if sz >= 16 else "sans", sz, VB)

    # diagonal SPECIMEN watermark (low alpha — does not obscure OCR)
    wm = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wm)
    wf = font("sansb", S(34))
    for row in range(-1, 6):
        for col in range(-1, 4):
            wd.text((col * S(360) - S(40), row * S(120) + S(150)),
                    "SPECIMEN  •  NOT A REAL DOCUMENT", font=wf, fill=(120, 130, 140, 26))
    wm = wm.rotate(28, resample=Image.BICUBIC, center=(W // 2, H // 2))
    img = Image.alpha_composite(img.convert("RGBA"), wm).convert("RGB")
    d = ImageDraw.Draw(img)

    def text2(xy, s, key, size, fill, anchor="la"):
        d.text((S(xy[0]), S(xy[1])), s, font=font(key, S(size)), fill=fill, anchor=anchor)

    # footer disclaimer + MRZ band (MRZ printed AFTER watermark so it stays crisp)
    text2((500, 460), "Generated synthetic test data — pearson-demo-cases / "
          "synthetic-passports — not a government document.", "sans", 10, "#7a8893", anchor="ma")
    d.rectangle([0, S(486), W, S(566)], fill="#ffffff")
    l1, l2 = mrz
    d.text((S(26), S(506)), l1, font=font("mono", S(26)), fill="#10222f")
    d.text((S(26), S(540)), l2, font=font("mono", S(26)), fill="#10222f")
    text2((500, 590), "SPECIMEN — NOT A REAL DOCUMENT — SYNTHETIC TEST DATA ONLY",
          "sansb", 11, "#b00020", anchor="ma")

    if SS != 1:
        img = img.resize((width, int(width * 0.64)), Image.LANCZOS)
    return img


# ── image-quality variations ─────────────────────────────────────────────────
def apply_quality(img: Image.Image, quality: str, rng: random.Random):
    """Return (image, file_ext, save_kwargs). Default ext is png."""
    ext, save = "png", {}
    if quality == "clean":
        pass
    elif quality == "blur":
        img = img.filter(ImageFilter.GaussianBlur(radius=1.1))
    elif quality == "noise":
        if np is not None:
            a = np.asarray(img).astype(np.int16)
            a += rng_normal(rng, a.shape, 14)
            img = Image.fromarray(np.clip(a, 0, 255).astype("uint8"))
        else:
            img = img.filter(ImageFilter.GaussianBlur(0.6))
    elif quality == "low_res":
        w, h = img.size
        small = img.resize((int(w * 0.5), int(h * 0.5)), Image.BILINEAR)
        img = small.resize((w, h), Image.BILINEAR)
    elif quality == "rotate":
        img = img.rotate(rng.uniform(-4, 4), resample=Image.BICUBIC, expand=True,
                         fillcolor=(235, 238, 242))
    elif quality == "skew":
        if np is not None:
            w, h = img.size
            j = lambda: rng.uniform(0.0, 0.05)
            src = [(0, 0), (w, 0), (w, h), (0, h)]
            dst = [(w * j(), h * j()), (w * (1 - j()), h * j()),
                   (w * (1 - j()), h * (1 - j())), (w * j(), h * (1 - j()))]
            img = img.transform((w, h), Image.PERSPECTIVE, _find_coeffs(src, dst),
                                Image.BICUBIC, fillcolor=(235, 238, 242))
        else:
            img = img.rotate(3, resample=Image.BICUBIC, expand=True, fillcolor=(235, 238, 242))
    elif quality == "jpeg":
        ext, save = "jpg", {"quality": 32}
    elif quality == "grayscale":
        img = ImageOps.grayscale(img).convert("RGB")
    elif quality == "glare":
        w, h = img.size
        ov = Image.new("L", (w, h), 0)
        od = ImageDraw.Draw(ov)
        gx, gy = rng.randint(0, w), rng.randint(0, int(h * 0.5))
        od.ellipse([gx - w * 0.3, gy - h * 0.3, gx + w * 0.3, gy + h * 0.3], fill=150)
        ov = ov.filter(ImageFilter.GaussianBlur(60))
        white = Image.new("RGB", (w, h), (255, 255, 255))
        img = Image.composite(white, img, ov)
    elif quality == "dark":
        img = ImageEnhance.Brightness(img).enhance(0.58)
    elif quality == "low_contrast":
        img = ImageEnhance.Contrast(img).enhance(0.55)
    return img, ext, save


def rng_normal(rng: random.Random, shape, sigma):
    """Deterministic gaussian noise array from a python RNG (seeds numpy locally)."""
    st = np.random.RandomState(rng.randint(0, 2**31 - 1))
    return st.normal(0, sigma, shape).astype(np.int16)


# ── one record ───────────────────────────────────────────────────────────────
def corrupt_mrz_line2(l2: str) -> str:
    """Flip the final composite check digit so it no longer validates."""
    bad = str((int(l2[43]) + 1) % 10)
    return l2[:43] + bad


def generate_one(code: str, idx: int, quality: str, defect: str, seed, as_of: dt.date,
                 out_dir: str, width: int) -> dict:
    rng = random.Random(f"{seed}|{code}|{idx}|{quality}|{defect}")
    p = synth_person(code, rng, as_of)
    inst = apply_defect(p, defect, rng, as_of)

    l1, l2 = build_mrz(p)                    # valid MRZ from the TRUE identity
    if inst["mrz_corrupt"]:
        l2 = corrupt_mrz_line2(l2)
    mrz_valid = mrz_checkdigits_valid(l2)

    img = render_passport(p, (l1, l2), inst, width=width)
    img, ext, save = apply_quality(img, quality, rng)

    stem = f"{code.lower()}-{idx:04d}-{quality}-{defect}"
    cdir = os.path.join(out_dir, code)
    os.makedirs(cdir, exist_ok=True)
    img_path = os.path.join(cdir, f"{stem}.{ext}")
    img.convert("RGB").save(img_path, **save)

    rel = os.path.relpath(img_path, out_dir)
    record = {
        "id": stem,
        "synthetic": True,
        "disclaimer": "Synthetic specimen for software testing only. Fictional data; "
                      "stylized non-official design; not a real or valid passport.",
        "image": rel,
        "country": code,
        "country_display": COUNTRIES[code]["display"],
        "fields": {
            "surname": p["surname"],
            "given_names": p["given"],
            "nationality": p["nationality"],
            "nationality_display": p["nationality_long"],
            "sex": p["sex"],
            "date_of_birth": p["dob"],
            "place_of_birth": p["place_of_birth"],
            "passport_number": p["passport_number"],
            "date_of_issue": p["passport_issue"],
            "date_of_expiry": p["passport_expiration"],
            "issuing_authority": p["authority"],
        },
        "mrz": {"line1": l1, "line2": l2, "checkdigits_valid": mrz_valid},
        "variations": {"quality": quality, "defect": defect,
                       "printed_overrides": inst["visible"],
                       "blanked_fields": inst["blank"],
                       "date_style": inst["date_style"]},
        "expected_review_flags": inst["expected_flags"],
        "as_of": iso(as_of),
        "seed": str(seed),
        "image_sha256": hashlib.sha256(open(img_path, "rb").read()).hexdigest(),
    }
    with open(os.path.join(cdir, f"{stem}.json"), "w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    return record


# ── batch + presets ──────────────────────────────────────────────────────────
def resolve_set(arg: str, universe: list) -> list:
    if arg in ("all", "mix"):
        return list(universe)
    items = [x.strip() for x in arg.split(",") if x.strip()]
    bad = [x for x in items if x not in universe]
    if bad:
        sys.exit(f"unknown value(s): {bad}\nvalid: {universe}")
    return items


def write_manifest(out_dir: str, records: list):
    records = sorted(records, key=lambda r: r["id"])
    with open(os.path.join(out_dir, "manifest.jsonl"), "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # human-readable summary
    by_country = {}
    flags = {}
    for r in records:
        by_country[r["country"]] = by_country.get(r["country"], 0) + 1
        for fl in r["expected_review_flags"]:
            flags[fl] = flags.get(fl, 0) + 1
    lines = ["# Synthetic passport dataset — summary", "",
             f"- Total documents: **{len(records)}**",
             f"- Countries: {', '.join(f'{k} ({v})' for k, v in sorted(by_country.items()))}",
             "", "## Expected review flags (the oracle for LEI's gates)", ""]
    if flags:
        for k, v in sorted(flags.items()):
            lines.append(f"- `{k}`: {v}")
    else:
        lines.append("- (all clean — no defect flags)")
    lines += ["", "Each `*.json` sidecar is the ground truth for its image. "
              "`manifest.jsonl` aggregates them.", ""]
    with open(os.path.join(out_dir, "DATASET.md"), "w") as f:
        f.write("\n".join(lines))


def cmd_generate(args):
    countries = resolve_set(args.countries, ORDER)
    qualities = resolve_set(args.quality, QUALITY_VARIANTS)
    defects = resolve_set(args.defects, DEFECT_VARIANTS)
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else DEFAULT_AS_OF
    os.makedirs(args.out, exist_ok=True)
    recs = []
    for code in countries:
        crng = random.Random(f"{args.seed}|pick|{code}")
        for i in range(args.per_country):
            q = crng.choice(qualities)
            de = crng.choice(defects)
            recs.append(generate_one(code, i, q, de, args.seed, as_of, args.out, args.width))
    write_manifest(args.out, recs)
    print(f"generated {len(recs)} docs across {len(countries)} countries -> {args.out}")


# Curated deterministic matrix: every country gets clean + a defect spread + a few
# quality variants. Stable so the committed sample set doesn't churn.
SAMPLE_MATRIX = [
    ("clean", "none"),
    ("clean", "expired"),
    ("clean", "near_expiry"),
    ("clean", "mrz_checkdigit_corrupt"),
    ("clean", "mrz_visible_mismatch"),
    ("clean", "missing_field"),
    ("clean", "date_format_variant"),
    ("blur", "none"),
    ("jpeg", "none"),
    ("low_res", "none"),
    ("rotate", "none"),
    ("noise", "expired"),
]


def cmd_sample(args):
    as_of = DEFAULT_AS_OF
    os.makedirs(args.out, exist_ok=True)
    recs = []
    for code in ORDER:
        for i, (q, de) in enumerate(SAMPLE_MATRIX):
            recs.append(generate_one(code, i, q, de, args.seed, as_of, args.out, args.width))
    write_manifest(args.out, recs)
    print(f"sample set: {len(recs)} docs ({len(ORDER)} countries x {len(SAMPLE_MATRIX)}) -> {args.out}")


def cmd_validate(args):
    mpath = os.path.join(args.out, "manifest.jsonl")
    if not os.path.exists(mpath):
        sys.exit(f"no manifest at {mpath}")
    n = ok = 0
    problems = []
    with open(mpath) as f:
        for line in f:
            r = json.loads(line)
            n += 1
            img = os.path.join(args.out, r["image"])
            if not os.path.exists(img):
                problems.append(f"{r['id']}: missing image {r['image']}")
                continue
            if not os.path.exists(os.path.join(args.out, r["country"], r["id"] + ".json")):
                problems.append(f"{r['id']}: missing json sidecar")
                continue
            # MRZ check-digit consistency must match the recorded flag
            valid = mrz_checkdigits_valid(r["mrz"]["line2"])
            corrupt_expected = "mrz_checkdigit_invalid" in r["expected_review_flags"]
            if valid == corrupt_expected:
                problems.append(f"{r['id']}: MRZ valid={valid} but corrupt_expected={corrupt_expected}")
                continue
            if valid != r["mrz"]["checkdigits_valid"]:
                problems.append(f"{r['id']}: recorded checkdigits_valid mismatch")
                continue
            ok += 1
    print(f"validate: {ok}/{n} OK")
    for p in problems[:40]:
        print("  FAIL", p)
    sys.exit(1 if problems else 0)


def cmd_list(args):
    print(f"{'CODE':5} {'COUNTRY':18} {'SCRIPT':10} EMBLEM")
    for code in ORDER:
        c = COUNTRIES[code]
        print(f"{code:5} {c['display']:18} {c['native_font']:10} {c['emblem']}")
    print(f"\nqualities: {QUALITY_VARIANTS}")
    print(f"defects:   {DEFECT_VARIANTS}")


def main():
    ap = argparse.ArgumentParser(description="Synthetic passport dataset generator (test data only).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate N docs per country with controlled variations")
    g.add_argument("--countries", default="all", help="'all' or CSV of codes, e.g. IND,MEX")
    g.add_argument("--per-country", type=int, default=3)
    g.add_argument("--quality", default="clean", help="'mix'/'all' or CSV of quality variants")
    g.add_argument("--defects", default="none", help="'mix'/'all' or CSV of defect variants")
    g.add_argument("--seed", default="1")
    g.add_argument("--as-of", default=None, help="reference 'today' (YYYY-MM-DD) for expiry math")
    g.add_argument("--width", type=int, default=1000)
    g.add_argument("--out", default=DEFAULT_OUT)
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("sample", help="curated deterministic baseline set (commit-friendly)")
    s.add_argument("--seed", default="1")
    s.add_argument("--width", type=int, default=1000)
    s.add_argument("--out", default=DEFAULT_OUT)
    s.set_defaults(func=cmd_sample)

    v = sub.add_parser("validate", help="re-check MRZ check digits + sidecar integrity")
    v.add_argument("--out", default=DEFAULT_OUT)
    v.set_defaults(func=cmd_validate)

    l = sub.add_parser("list-countries", help="show the country/emblem/variant catalog")
    l.set_defaults(func=cmd_list)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
