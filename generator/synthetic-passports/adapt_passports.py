#!/usr/bin/env python3
"""adapt_passports.py — adapt a REAL, permissively-licensed passport specimen/template
into a FICTIONAL-identity SPECIMEN by overlaying synthetic fields + a valid ICAO-9303
MRZ onto the real layout. Higher visual fidelity than the from-scratch generator, while
staying clearly-synthetic (SPECIMEN overprint + notice strip + disclaimer in the JSON).

PROOF stage: Pakistan polycarbonate e-passport template (CC BY-SA 4.0, blank fields —
the cleanest base, needs no inpainting). See REFERENCES.md for sourcing + licenses.

Boundary: only government/ICAO specimens, anonymized templates, or CC/PD images,
adapted to FICTIONAL identities. Never a real, identifiable live passport.

Usage:
  python3 adapt_passports.py --reference /path/to/pakistan_poly.png --count 1 --seed 1 --out out_adapt
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import random

from PIL import Image, ImageDraw

import synth_passports as S
from countries import COUNTRIES

HERE = os.path.dirname(os.path.abspath(__file__))

# Per-template field map in the template's NATIVE pixel coords (x, y, w, h).
# Auto-detected from the template's grey value-boxes, then mapped to fields.
PAK_TEMPLATE = {
    "code": "PAK",
    "size": (1280, 865),
    "license": "CC BY-SA 4.0",
    "attribution": "Data Page - Polycarbonate Page of Pakistani Passport, "
                   "MuhammadSarimShoukat, CC BY-SA 4.0, via Wikimedia Commons "
                   "(adapted: fictional identity overlaid, marked SPECIMEN)",
    "source_url": "https://commons.wikimedia.org/wiki/"
                  "File:Data_Page_-_Polycarbonate_Page_of_Pakistani_Passport.png",
    "fields": {
        "passport_number": (787, 114, 150, 31),
        "surname": (417, 160, 160, 27),
        "given": (421, 210, 160, 23),
        "date_of_birth": (422, 307, 175, 24),
        "sex": (421, 354, 55, 24),
        "place_of_birth": (560, 354, 175, 27),
        "father_name": (420, 404, 300, 26),
        "religion": (421, 453, 160, 22),
        "date_of_issue": (419, 500, 175, 25),
        "date_of_expiry": (419, 549, 175, 25),
        "tracking_number": (418, 598, 185, 26),
        "citizenship_no": (788, 310, 215, 25),
        "booklet_number": (789, 551, 150, 23),
        "previous_passport": (788, 601, 160, 23),
    },
    "photo": (59, 213, 313, 435),
    "mrz_band": (34, 744, 1212, 74),   # full bottom band — repainted with a fresh MRZ
}


def _sample_bg(img, x, y, w, h):
    """A light field color sampled from just right of the box, blended toward white."""
    W, H = img.size
    sx, sy = min(x + w + 8, W - 1), min(y + h // 2, H - 1)
    r, g, b = img.getpixel((sx, sy))[:3]
    mix = lambda c: int(c * 0.35 + 255 * 0.65)   # 65% toward white = clean field
    return (mix(r), mix(g), mix(b))


def _fit_font(key, box_h, max_pt=26):
    return S.font(key, min(max_pt, max(11, int(box_h * 0.74))))


def adapt_one(template_path: str, tmpl: dict, idx: int, seed, as_of: dt.date,
              out_dir: str) -> dict:
    code = tmpl["code"]
    rng = random.Random(f"adapt|{code}|{seed}|{idx}")
    p = S.synth_person(code, rng, as_of)

    # Pakistan-specific extra fields (plausible synthetic values)
    father = f"{rng.choice(COUNTRIES[code]['given_m'])} {p['surname']}"
    cnic = f"{rng.randint(10000,99999)}-{rng.randint(1000000,9999999)}-{rng.randint(1,9)}"
    booklet = f"{rng.choice('ABCDEFGHJKLMNP')}{rng.randint(1000000,9999999)}"
    tracking = f"{rng.randint(100000000,999999999)}"

    shown = {
        "passport_number": p["passport_number"],
        "surname": p["surname"].upper(),
        "given": p["given"].upper(),
        "date_of_birth": S.fmt_date(p["dob"]),
        "sex": p["sex"],
        "place_of_birth": p["place_of_birth"].upper(),
        "father_name": father.upper(),
        "religion": "ISLAM",
        "date_of_issue": S.fmt_date(p["passport_issue"]),
        "date_of_expiry": S.fmt_date(p["passport_expiration"]),
        "tracking_number": tracking,
        "citizenship_no": cnic,
        "booklet_number": booklet,
        "previous_passport": "",
    }

    img = Image.open(template_path).convert("RGB")
    # If a higher-res copy of the same template is supplied, scale the map proportionally.
    sx = img.size[0] / tmpl["size"][0]
    sy = img.size[1] / tmpl["size"][1]

    def S_(x, y, w, h):
        return int(x * sx), int(y * sy), int(w * sx), int(h * sy)

    d = ImageDraw.Draw(img)

    # 1. overlay field values (clear the grey box, print the value)
    for field, (x, y, w, h) in tmpl["fields"].items():
        val = shown.get(field, "")
        if not val:
            continue
        bx, by, bw, bh = S_(x, y, w, h)
        d.rectangle([bx, by, bx + bw, by + bh], fill=_sample_bg(img, bx, by, bw, bh))
        d.text((bx + 4, by + bh / 2), val, font=_fit_font("sansb", bh),
               fill="#1a1a1a", anchor="lm")

    # 2. placeholder silhouette in the photo oval (never a real face)
    px, py, pw, ph = S_(*tmpl["photo"])
    cx = px + pw // 2
    d.ellipse([cx - pw * 0.28, py + ph * 0.18, cx + pw * 0.28, py + ph * 0.50], fill="#9aa6ad")
    d.pieslice([cx - pw * 0.42, py + ph * 0.46, cx + pw * 0.42, py + ph * 0.95], 180, 360, fill="#9aa6ad")
    d.text((cx, py + ph - int(20 * sy)), "SPECIMEN", font=S.font("sansb", int(18 * sy)),
           fill="#5f6e77", anchor="mm")

    # 3. fresh valid ICAO-9303 MRZ over the bottom band (covers the template's partial print)
    l1, l2 = S.build_mrz(p)
    mx, my, mw, mh = S_(*tmpl["mrz_band"])
    d.rectangle([mx, my, mx + mw, my + mh], fill="#f5f6f2")
    mono = S.font("mono", int(26 * min(sx, sy)))
    d.text((mx + int(20 * sx), my + int(14 * sy)), l1, font=mono, fill="#10141a")
    d.text((mx + int(20 * sx), my + int(42 * sy)), l2, font=mono, fill="#10141a")

    # 4. SPECIMEN marking — diagonal watermark + bottom notice strip (clearly synthetic)
    W, H = img.size
    wm = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wm)
    wf = S.font("sansb", int(46 * min(sx, sy)))
    for row in range(-1, 7):
        for col in range(-1, 3):
            wd.text((col * int(470 * sx) - int(40 * sx), row * int(150 * sy) + int(120 * sy)),
                    "SPECIMEN", font=wf, fill=(150, 40, 40, 34))
    wm = wm.rotate(28, resample=Image.BICUBIC, center=(W // 2, H // 2))
    img = Image.alpha_composite(img.convert("RGBA"), wm).convert("RGB")
    d = ImageDraw.Draw(img)
    strip_h = int(30 * sy)
    d.rectangle([0, H - strip_h, W, H], fill="#b00020")
    d.text((W // 2, H - strip_h // 2),
           "SYNTHETIC SPECIMEN  ·  FICTITIOUS TEST DATA  ·  NOT A REAL PASSPORT  ·  "
           "NOT VALID FOR TRAVEL OR IDENTITY", font=S.font("sansb", int(13 * sy)),
           fill="#ffffff", anchor="mm")

    # 5. save + ground-truth sidecar
    stem = f"{code.lower()}-adapt-{idx:04d}"
    cdir = os.path.join(out_dir, code)
    os.makedirs(cdir, exist_ok=True)
    img_path = os.path.join(cdir, f"{stem}.png")
    img.save(img_path)

    record = {
        "id": stem,
        "synthetic": True,
        "method": "adapt-real-specimen",
        "disclaimer": "Synthetic specimen for software testing only. A fictional "
                      "identity overlaid on a permissively-licensed passport template; "
                      "marked SPECIMEN. Not a real or valid passport.",
        "image": os.path.relpath(img_path, out_dir),
        "country": code,
        "country_display": COUNTRIES[code]["display"],
        "base_reference": {
            "license": tmpl["license"],
            "attribution": tmpl["attribution"],
            "source_url": tmpl["source_url"],
        },
        "fields": {
            "surname": p["surname"], "given_names": p["given"],
            "nationality": p["nationality"], "nationality_display": p["nationality_long"],
            "sex": p["sex"], "date_of_birth": p["dob"],
            "place_of_birth": p["place_of_birth"], "passport_number": p["passport_number"],
            "date_of_issue": p["passport_issue"], "date_of_expiry": p["passport_expiration"],
            "father_name": father, "citizenship_number": cnic,
        },
        "mrz": {"line1": l1, "line2": l2,
                "checkdigits_valid": S.mrz_checkdigits_valid(l2)},
        "expected_review_flags": [],
        "as_of": S.iso(as_of), "seed": str(seed),
        "image_sha256": hashlib.sha256(open(img_path, "rb").read()).hexdigest(),
    }
    with open(os.path.join(cdir, f"{stem}.json"), "w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    return record


def main():
    ap = argparse.ArgumentParser(description="Adapt a real passport specimen into a fictional SPECIMEN.")
    ap.add_argument("--reference", required=True, help="path to the Pakistan template image")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--seed", default="1")
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "out_adapt"))
    args = ap.parse_args()
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else S.DEFAULT_AS_OF
    os.makedirs(args.out, exist_ok=True)
    recs = [adapt_one(args.reference, PAK_TEMPLATE, i, args.seed, as_of, args.out)
            for i in range(args.count)]
    print(f"adapted {len(recs)} doc(s) -> {args.out}")


if __name__ == "__main__":
    main()
