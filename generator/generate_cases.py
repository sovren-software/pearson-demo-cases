#!/usr/bin/env python3
"""Generate 3 synthetic H-1B case files for the Pearson synthetic-case corpus.

Each profile gets a complete, extractor-ready intake packet under
cases/h1b/<slug>/:
  passport.png      — country-styled synthetic data page (India / China / Mexico
                      national colors, bilingual header, stylized emblem). The
                      bottom MRZ is a valid ICAO 9303 TD3 zone (check digits
                      computed + self-validated here). Marked SPECIMEN.
  offer.pdf         — employment offer letter (employment-grammar fields).
  lca.pdf           — certified ETA-9035 Labor Condition Application.
  i94.pdf           — CBP I-94 arrival/departure record (i94 extractor fields).
  degree.pdf        — diploma / credential evaluation (degree extractor fields).
  support-letter.pdf— employer specialty-occupation support letter.
  ground-truth.json — every expected fact (the accuracy check) + the
                      pre-authored material-change email body for Act 2.

ALL DATA IS FICTIONAL / SYNTHETIC — no real PII; emblems are stylized (not real
state emblems) and every passport is watermarked SPECIMEN. Field wording matches
the employment-extraction grammar.

Run:  python3 generator/generate_cases.py
"""
import copy
import json
import math
import os
import shutil
import subprocess
import sys

REPO = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_ROOT = os.path.join(REPO, "cases", "h1b")
ADV_OUT_ROOT = os.path.join(REPO, "cases", "h1b-adversarial")
INC_OUT_ROOT = os.path.join(REPO, "cases", "h1b-incomplete")

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
MONTHS_LONG = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


# ── ICAO 9303 TD3 MRZ ────────────────────────────────────────────────────────
def check_digit(s: str) -> str:
    w = [7, 3, 1]
    t = 0
    for i, c in enumerate(s):
        if c == "<":
            v = 0
        elif c.isdigit():
            v = int(c)
        else:
            v = ord(c) - 55  # A=10 .. Z=35
        t += v * w[i % 3]
    return str(t % 10)


def mrz_name_field(surname: str, given: str) -> str:
    s = surname.upper().replace(" ", "<")
    g = given.upper().replace(" ", "<")
    return (f"{s}<<{g}" + "<" * 39)[:39]


def build_mrz(p: dict):
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


def human_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(d):02d} {MONTHS[int(m) - 1]} {y}"


def long_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{MONTHS_LONG[int(m) - 1]} {int(d)}, {y}"


# ── fonts ────────────────────────────────────────────────────────────────────
def fc(query: str, fallback: str) -> str:
    try:
        out = subprocess.check_output(["fc-match", "-f", "%{file}", query],
                                      text=True, stderr=subprocess.DEVNULL).strip()
        return out or fallback
    except Exception:
        return fallback


SANS = fc("DejaVu Sans", "DejaVu-Sans")
SANSB = fc("DejaVu Sans:bold", SANS)
MONO = fc("JetBrains Mono", fc("DejaVu Sans Mono", SANS))
DEVA = fc("Noto Sans Devanagari", SANS)   # Hindi
CJK = fc("Noto Sans CJK SC", SANS)        # Chinese


# ── per-country passport style ───────────────────────────────────────────────
STYLES = {
    "IND": {
        "header": "#10235e", "tint": "#eef2f8", "accent": "#ff9933",
        "country_native": "भारत गणराज्य", "country_font": DEVA, "country_color": "#ffffff",
        "country_en": "REPUBLIC OF INDIA",
        "passport_native": "पासपोर्ट", "passport_font": DEVA,
        "emblem": "chakra", "emblem_color": "#ff9933",
        "authority": "Ministry of External Affairs, Government of India",
    },
    "CHN": {
        "header": "#c8102e", "tint": "#f7eeee", "accent": "#ffd200",
        "country_native": "中华人民共和国", "country_font": CJK, "country_color": "#ffd200",
        "country_en": "PEOPLE'S REPUBLIC OF CHINA",
        "passport_native": "护照", "passport_font": CJK,
        "emblem": "stars", "emblem_color": "#ffd200",
        "authority": "National Immigration Administration",
    },
    "MEX": {
        "header": "#006847", "tint": "#eaf3ee", "accent": "#ce1126",
        "country_native": "ESTADOS UNIDOS MEXICANOS", "country_font": SANSB, "country_color": "#ffffff",
        "country_en": "UNITED MEXICAN STATES",
        "passport_native": "PASAPORTE", "passport_font": SANSB,
        "emblem": "seal", "emblem_color": "#ce1126",
        "authority": "Secretaría de Relaciones Exteriores",
    },
}


def emblem_args(kind: str, color: str, cx: int, cy: int, r: int):
    a = []
    if kind == "chakra":  # Ashoka-style wheel: ring + hub + 24 spokes
        a += ["-fill", "none", "-stroke", color, "-strokewidth", "2.4",
              "-draw", f"circle {cx},{cy} {cx},{cy - r}"]
        a += ["-stroke", color, "-strokewidth", "1.3"]
        for k in range(24):
            ang = math.radians(k * 15)
            x2 = cx + (r - 2) * math.cos(ang)
            y2 = cy + (r - 2) * math.sin(ang)
            a += ["-draw", f"line {cx},{cy} {x2:.1f},{y2:.1f}"]
        a += ["-fill", color, "-stroke", "none", "-draw", f"circle {cx},{cy} {cx},{cy - 4}"]
    elif kind == "stars":  # flag motif: one large + four small gold stars
        a += ["-fill", color, "-stroke", "none"]

        def star(scx, scy, ro):
            ri = ro * 0.42
            pts = []
            for i in range(10):
                ang = math.radians(-90 + i * 36)
                rr = ro if i % 2 == 0 else ri
                pts.append(f"{scx + rr * math.cos(ang):.1f},{scy + rr * math.sin(ang):.1f}")
            return "polygon " + " ".join(pts)

        a += ["-draw", star(cx - 8, cy, r * 0.62)]
        for (dx, dy) in [(14, -14), (22, -2), (22, 12), (14, 22)]:
            a += ["-draw", star(cx + dx, cy + dy, r * 0.22)]
    else:  # seal: concentric rings
        a += ["-fill", "none", "-stroke", color, "-strokewidth", "3",
              "-draw", f"circle {cx},{cy} {cx},{cy - r}"]
        a += ["-stroke", "#006847", "-strokewidth", "2",
              "-draw", f"circle {cx},{cy} {cx},{cy - (r - 7)}"]
        a += ["-fill", color, "-stroke", "none",
              "-draw", f"circle {cx},{cy} {cx},{cy - 4}"]
    a += ["-stroke", "none"]
    return a


def T(font, size, color, x, y, s, align=None):
    out = ["-font", font, "-pointsize", str(size), "-fill", color]
    if align:
        out += ["-gravity", align]
    out += ["-annotate", f"+{x}+{y}", s]
    if align:
        out += ["-gravity", "northwest"]
    return out


def render_passport(p: dict, out: str):
    l1, l2 = p["_mrz"]
    st = STYLES[p["nationality"]]
    args = ["-size", "1000x640", f"xc:{st['tint']}"]
    # header band
    args += ["-fill", st["header"], "-stroke", "none", "-draw", "rectangle 0,0 1000,108"]
    # emblem (left of header)
    args += emblem_args(st["emblem"], st["emblem_color"], 58, 54, 34)
    # country name (native + english) + passport word
    args += T(st["country_font"], 28, st["country_color"], 112, 46, st["country_native"])
    args += T(SANS, 15, "#dfe6f0", 112, 80, st["country_en"])
    args += T(st["passport_font"], 26, st["country_color"], 712, 44, st["passport_native"])
    args += T(SANS, 14, "#dfe6f0", 712, 76, "PASSPORT")
    args += T(SANS, 11, st["accent"], 858, 98, "SPECIMEN")
    # type / code / passport no. strip
    args += T(SANS, 12, "#5b6b78", 300, 138, "Type / P     Code / " + p["nationality"]
              + "     Passport No.")
    args += T(SANSB, 20, "#10222f", 640, 162, p["passport_number"].upper())
    # photo box
    args += ["-fill", "#d4dde4", "-stroke", "#9fb0bc", "-strokewidth", "1",
             "-draw", "rectangle 40,160 250,410", "-stroke", "none"]
    args += T(SANS, 17, "#62727f", 112, 292, "PHOTO")
    # field labels (grey) + values (dark bold)
    LB, VB = "#5b6b78", "#10222f"
    args += T(SANS, 13, LB, 300, 150, "Surname")
    args += T(SANSB, 22, VB, 300, 180, p["surname"].upper())
    args += T(SANS, 13, LB, 300, 214, "Given names")
    args += T(SANSB, 22, VB, 300, 244, p["given"].upper())
    args += T(SANS, 13, LB, 300, 278, "Nationality")
    args += T(SANSB, 19, VB, 300, 305, f"{p['nationality_long'].upper()} / {p['nationality']}")
    args += T(SANS, 13, LB, 300, 339, "Date of birth")
    args += T(SANSB, 19, VB, 300, 366, human_date(p["dob"]))
    args += T(SANS, 13, LB, 640, 278, "Sex")
    args += T(SANSB, 19, VB, 640, 305, p["sex"])
    args += T(SANS, 13, LB, 720, 278, "Place of birth")
    args += T(SANSB, 17, VB, 720, 305, p["place_of_birth"].upper())
    args += T(SANS, 13, LB, 640, 339, "Date of issue")
    args += T(SANSB, 19, VB, 640, 366, human_date(p["passport_issue"]))
    args += T(SANS, 13, LB, 300, 398, "Date of expiry")
    args += T(SANSB, 19, VB, 300, 425, human_date(p["passport_expiration"]))
    args += T(SANS, 13, LB, 640, 398, "Authority")
    args += T(SANS, 13, VB, 640, 423, st["authority"])
    # faint diagonal SPECIMEN watermark across the body
    args += ["-font", SANSB, "-pointsize", "60", "-fill", "rgba(120,130,140,0.10)",
             "-annotate", "330x330+150+430", "SPECIMEN  •  NOT A REAL DOCUMENT"]
    # MRZ band (UNCHANGED — the functional zone the VLM reads)
    args += ["-fill", "#ffffff", "-stroke", "none", "-draw", "rectangle 0,468 1000,640"]
    args += ["-font", MONO, "-pointsize", "30", "-fill", "#10222f",
             "-annotate", "+24+538", l1, "-annotate", "+24+590", l2]
    subprocess.run(["magick", *args, out], check=True)


# ── HTML document templates ──────────────────────────────────────────────────
DOC_CSS = """body{font-family:'Liberation Serif','DejaVu Serif',serif;font-size:12pt;
margin:56px;line-height:1.5;color:#111;}
h1{font-size:17pt;color:#16324f;margin-bottom:2px;}
.meta{color:#444;font-size:10.5pt;margin-top:0;}
hr{border:none;border-top:1px solid #889;margin:12px 0 16px;}
table{border-collapse:collapse;font-size:11pt;width:100%;}
td{padding:3px 10px 3px 0;vertical-align:top;}
td.k{color:#445;width:38%;}
b{color:#10222f;} .sig{margin-top:40px;}
.stamp{color:#1d6b3a;border:1.5px solid #1d6b3a;display:inline-block;padding:3px 10px;
font-size:10pt;letter-spacing:.05em;margin-top:8px;}"""


def page(body: str) -> str:
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{DOC_CSS}</style></head><body>{body}</body></html>"


def offer_html(p: dict) -> str:
    # REALISM: a real employer offer letter states title / salary / worksite /
    # start date — NOT the SOC/O*NET code, the prevailing wage, or the EIN. Those
    # live on the LCA (ETA-9035), the I-129, and the petition/support letter. Do
    # NOT re-add SOC or EIN here — the cross-document validators source them from
    # those documents (see VALIDATION-SPEC.md: soc_code_mismatch / employer_ein_mismatch).
    e = p["employer"]
    # `_omit_wage` (incomplete tier) → the offer is present but states no salary, so the
    # required wage FIELD is missing while the document itself is not.
    if p.get("_omit_wage"):
        comp = ("Your compensation package will be competitive and market-aligned; the exact "
                "annualized base salary will be confirmed in a separate salary addendum prior to filing.")
    else:
        comp = (f"Your annualized base salary will be <b>${p['annual_wage_usd']:,} USD</b>, paid "
                "semi-monthly, which meets or exceeds the prevailing wage for this occupation and worksite.")
    return page(f"""
  <h1>{e['name']}</h1>
  <p class='meta'>{e['address']}</p><hr>
  <p>{long_date(p['requested_start_date'])}</p>
  <p>{p['given'].title()} {p['surname'].title()}</p>
  <p>Dear {p['given'].title()} {p['surname'].title()},</p>
  <p>We are pleased to offer you the position of <b>{p['job_title']}</b> at {e['name']}.
     This letter confirms the terms of your full-time employment, which will be the basis of the
     H-1B petition (Form I-129) the Company will file on your behalf.</p>
  <p><b>Position.</b> {p['job_title']}, a full-time
     specialty occupation requiring at minimum a {p['degree_min']} in {p['degree_field']} or a
     closely related field.</p>
  <p><b>Compensation.</b> {comp}</p>
  <p><b>Worksite.</b> Your primary place of employment will be {p['worksite_address']}.</p>
  <p><b>Employment period.</b> The requested period of employment is
     {long_date(p['requested_start_date'])} through {long_date(p['requested_end_date'])}.</p>
  <p>This offer is contingent upon approval of your H-1B petition and your maintenance of valid
     work authorization.</p>
  <p class='sig'>Sincerely,<br><br>{e['signer']}<br>{e['signer_title']}<br>{e['name']}</p>""")


def lca_html(p: dict) -> str:
    e = p["employer"]
    return page(f"""
  <h1>U.S. Department of Labor — Labor Condition Application (ETA-9035)</h1>
  <p class='meta'>Certified — Office of Foreign Labor Certification</p><hr>
  <table>
    <tr><td class='k'>LCA Case Number</td><td><b>{p['lca_case_number']}</b></td></tr>
    <tr><td class='k'>Case Status</td><td>CERTIFIED</td></tr>
    <tr><td class='k'>Visa Classification</td><td>H-1B</td></tr>
    <tr><td class='k'>Employer Legal Name</td><td>{e['name']}</td></tr>
    <tr><td class='k'>Employer EIN</td><td>{e['ein']}</td></tr>
    <tr><td class='k'>Employer Address</td><td>{e['address']}</td></tr>
    <tr><td class='k'>Job Title</td><td>{p['job_title']}</td></tr>
    <tr><td class='k'>SOC (O*NET) Code</td><td>{p['soc_code']}</td></tr>
    <tr><td class='k'>Full-Time Position</td><td>Yes (40 hours/week)</td></tr>
    <tr><td class='k'>Annual Wage Offered</td><td>${p['annual_wage_usd']:,} per year</td></tr>
    <tr><td class='k'>Prevailing Wage</td><td>${p['prevailing_wage']:,} per year (OES)</td></tr>
    <tr><td class='k'>Place of Employment</td><td>{p['worksite_address']}</td></tr>
    <tr><td class='k'>Period of Employment</td><td>{long_date(p['requested_start_date'])} &ndash; {long_date(p['requested_end_date'])}</td></tr>
  </table>
  <p class='stamp'>CERTIFIED &middot; ETA-9035</p>""")


def i94_html(p: dict) -> str:
    return page(f"""
  <h1>U.S. Customs and Border Protection</h1>
  <p class='meta'>I-94 Arrival/Departure Record &middot; Official Website Record</p><hr>
  <table>
    <tr><td class='k'>Most Recent I-94 Number</td><td><b>{p['i94_number']}</b></td></tr>
    <tr><td class='k'>Family Name</td><td>{p['surname'].upper()}</td></tr>
    <tr><td class='k'>First (Given) Name</td><td>{p['given'].upper()}</td></tr>
    <tr><td class='k'>Date of Birth</td><td>{human_date(p['dob'])}</td></tr>
    <tr><td class='k'>Most Recent Date of Entry</td><td>{long_date(p['i94_entry_date'])}</td></tr>
    <tr><td class='k'>Class of Admission</td><td><b>{p['current_nonimmigrant_status']}</b></td></tr>
    <tr><td class='k'>Admit Until Date</td><td>{p['i94_admit_until']}</td></tr>
    <tr><td class='k'>Passport Number</td><td>{p['passport_number'].upper()}</td></tr>
    <tr><td class='k'>Country of Citizenship</td><td>{p['nationality_long']}</td></tr>
  </table>""")


def degree_html(p: dict) -> str:
    d = p["degree"]
    if d.get("foreign"):
        return page(f"""
  <h1>Credential Evaluation Report</h1>
  <p class='meta'>{d['evaluator']} &middot; Course-by-Course Evaluation</p><hr>
  <p>This report evaluates the foreign academic credentials of <b>{p['given'].title()} {p['surname'].title()}</b>
     and certifies their United States educational equivalency.</p>
  <table>
    <tr><td class='k'>Credential Awarded</td><td>{d['original']}</td></tr>
    <tr><td class='k'>Awarding Institution</td><td>{d['institution']}</td></tr>
    <tr><td class='k'>Country</td><td>{p['nationality_long']}</td></tr>
    <tr><td class='k'>Year Awarded</td><td>{d['year']}</td></tr>
    <tr><td class='k'>U.S. Equivalency</td><td><b>{d['us_equivalent']} in {d['field']}</b></td></tr>
    <tr><td class='k'>Field of Study</td><td>{d['field']}</td></tr>
  </table>
  <p class='stamp'>EVALUATED &middot; U.S. EQUIVALENCY CONFIRMED</p>""")
    return page(f"""
  <h1>{d['institution']}</h1>
  <p class='meta'>Office of the Registrar &middot; Official Diploma / Degree Verification</p><hr>
  <p>This certifies that <b>{p['given'].title()} {p['surname'].title()}</b> was awarded the degree of:</p>
  <table>
    <tr><td class='k'>Degree</td><td><b>{d['us_equivalent']}</b></td></tr>
    <tr><td class='k'>Field of Study (Major)</td><td><b>{d['field']}</b></td></tr>
    <tr><td class='k'>Institution</td><td>{d['institution']}</td></tr>
    <tr><td class='k'>Date Conferred</td><td>{long_date(d['conferred'])}</td></tr>
  </table>""")


def support_html(p: dict) -> str:
    e = p["employer"]
    deps = ""
    if p.get("dependents"):
        names = ", ".join(f"{x['name']} ({x['relation']}, H-4)" for x in p["dependents"])
        deps = f"<p>The beneficiary will be accompanied by the following H-4 dependents: {names}.</p>"
    return page(f"""
  <h1>{e['name']} — Petition Support Letter</h1>
  <p class='meta'>{e['address']} &middot; EIN {e['ein']}</p><hr>
  <p>{long_date(p['requested_start_date'])}</p>
  <p>RE: H-1B Petition for {p['given'].title()} {p['surname'].title()} — {p['job_title']}</p>
  <p>To the U.S. Citizenship and Immigration Services:</p>
  <p>{e['name']} respectfully submits this petition to employ <b>{p['given'].title()} {p['surname'].title()}</b>
     in the specialty-occupation position of <b>{p['job_title']}</b> (SOC {p['soc_code']}) on a full-time basis
     at an annual salary of <b>${p['annual_wage_usd']:,}</b>.</p>
  <p><b>Specialty occupation.</b> The position requires the theoretical and practical application of a body of
     highly specialized knowledge and, at minimum, a {p['degree_min']} in {p['degree_field']} or a closely
     related field. {p['specialty_basis']}</p>
  <p><b>Beneficiary qualifications.</b> The beneficiary holds a {p['degree']['us_equivalent']} in
     {p['degree']['field']}, satisfying the minimum educational requirement for the position.</p>
  {deps}
  <p class='sig'>Respectfully submitted,<br><br>{e['signer']}<br>{e['signer_title']}<br>{e['name']}</p>""")


# ── extra "over-shared" client documents (the 'too-much' realism tier) ─────────
# A real client dumps everything they have, not just the 6 docs the I-129 needs.
# These render into the case folder so the demo shows the system ingesting a noisy
# packet gracefully — extract what's relevant, ignore the rest. NONE are required;
# ground-truth marks them required:false so they never count against the accuracy
# check (they corroborate at most). One of them (the résumé) spans two pages, so the
# corpus also exercises multi-page intake.

def _email(p: dict) -> str:
    sn = p["surname"].split()[0].lower()
    return f"{p['given'].lower()}.{sn}@mailbox.example"


def _phone(p: dict) -> str:
    # reserved-fictional 555-/206-555 range; deterministic per slug
    n = sum(ord(c) for c in p["slug"]) % 90 + 10
    return f"+1 (206) 555-{n:02d}71"


def _synth_id(p: dict, prefix: str, width: int) -> str:
    n = sum(ord(c) for c in (p["passport_number"] + prefix))
    return f"{prefix}{n % (10 ** width):0{width}d}"


def _current_payer(p: dict) -> str:
    # the employer that pays the beneficiary TODAY (often NOT the petitioner)
    return {
        "arjun-kumar": "DataBridge Labs, Inc. (F-1 OPT employer)",
        "yangben-zhengjian": p.get("prior_approval", {}).get("prior_employer", "Current Employer, Inc."),
        "abigail-medina": "Great Lakes Engineering Group (TN employer)",
    }.get(p["slug"], p["employer"]["name"])


RESUME_CSS = """body{font-family:'DejaVu Sans','Liberation Sans',sans-serif;font-size:10.5pt;
margin:46px 56px;line-height:1.42;color:#1a1a1a;}
h1{font-size:21pt;margin:0;color:#10222f;letter-spacing:.01em;}
.contact{color:#445;font-size:10pt;margin:3px 0 10px;}
h2{font-size:11pt;color:#16324f;border-bottom:1.5px solid #c3ccd4;padding-bottom:2px;
margin:15px 0 6px;text-transform:uppercase;letter-spacing:.06em;}
.role{font-weight:bold;color:#10222f;} .org{color:#334;}
.when{color:#667;font-size:9.5pt;float:right;}
ul{margin:4px 0 9px 18px;padding:0;} li{margin:2px 0;}
.sk{color:#334;}"""


def resume_html(p: dict) -> str:
    d = p["degree"]
    e = p["employer"]
    field = d["field"]
    prior = p.get("prior_approval", {}).get("prior_employer") or {
        "arjun-kumar": "DataBridge Labs, Inc.",
        "abigail-medina": "Hermosillo Automotriz, S.A. de C.V.",
    }.get(p["slug"], "Prior Employer, Inc.")
    body = f"""
  <h1>{p['given'].title()} {p['surname'].title()}</h1>
  <p class='contact'>{p['job_title']} &middot; {_email(p)} &middot; {_phone(p)}
     &middot; {p.get('us_physical_address', 'United States')}</p>
  <h2>Professional Summary</h2>
  <p>{p['job_title']} with deep expertise in {field.lower()}. Proven record of delivering
     production systems, leading technical initiatives, and mentoring engineers. Seeking to
     continue contributing in a specialty-occupation role at {e['name']}.</p>
  <h2>Experience</h2>
  <p><span class='when'>offer pending</span><span class='role'>{p['job_title']}</span> &mdash;
     <span class='org'>{e['name']}</span></p>
  <ul>
    <li>Own end-to-end {field.lower()} initiatives across design, implementation, and review.</li>
    <li>Partner across functions to ship reliable, scalable production systems.</li>
  </ul>
  <p><span class='when'>2019 &ndash; 2024</span><span class='role'>Engineer</span> &mdash;
     <span class='org'>{prior}</span></p>
  <ul>
    <li>Built and maintained core {field.lower()} components serving production workloads.</li>
    <li>Improved the performance and reliability of mission-critical data pipelines.</li>
    <li>Translated stakeholder requirements into delivered, tested features.</li>
  </ul>
  <p><span class='when'>2016 &ndash; 2019</span><span class='role'>Associate Engineer</span> &mdash;
     <span class='org'>Foundery Systems</span></p>
  <ul>
    <li>Supported development and testing across the engineering organization.</li>
    <li>Contributed to internal tooling, code review, and documentation.</li>
  </ul>
  <h2>Education</h2>
  <p><span class='role'>{d['us_equivalent']} in {field}</span> &mdash; {d['institution']}</p>
  <p>Relevant coursework: algorithms, systems design, statistics, and {field.lower()} fundamentals.</p>
  <h2>Skills</h2>
  <p class='sk'>{field}; systems design; data modeling; testing &amp; verification;
     cross-functional collaboration; technical writing; mentorship; production operations;
     performance tuning; stakeholder communication.</p>
  <h2>References</h2>
  <p>Available upon request.</p>"""
    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<style>{RESUME_CSS}</style></head><body>{body}</body></html>")


def i20_html(p: dict) -> str:  # F-1 / OPT student record (arjun)
    d = p["degree"]
    return page(f"""
  <h1>Form I-20 — Certificate of Eligibility for Nonimmigrant Student Status</h1>
  <p class='meta'>Student and Exchange Visitor Program (SEVP) &middot; Department of Homeland Security</p><hr>
  <table>
    <tr><td class='k'>SEVIS ID</td><td><b>{_synth_id(p, 'N', 10)}</b></td></tr>
    <tr><td class='k'>Surname / Given Name</td><td>{p['surname'].upper()} / {p['given'].upper()}</td></tr>
    <tr><td class='k'>Country of Birth / Citizenship</td><td>{p['nationality_long']}</td></tr>
    <tr><td class='k'>Class of Admission</td><td><b>F-1</b></td></tr>
    <tr><td class='k'>School</td><td>{d['institution']}</td></tr>
    <tr><td class='k'>Program of Study</td><td>{d['us_equivalent']} in {d['field']}</td></tr>
    <tr><td class='k'>Employment Authorization</td><td>Post-Completion OPT (STEM)</td></tr>
    <tr><td class='k'>OPT Authorized Period</td><td>{long_date('2024-07-01')} &ndash; {long_date('2027-06-30')}</td></tr>
  </table>
  <p class='stamp'>STUDENT COPY &middot; NOT FOR I-129 ACTION</p>""")


def i797_prior_html(p: dict) -> str:  # prior H-1B approval notice (zhengjian, transfer)
    pa = p.get("prior_approval", {})
    return page(f"""
  <h1>Form I-797C, Notice of Action</h1>
  <p class='meta'>U.S. Citizenship and Immigration Services &middot; Approval Notice</p><hr>
  <table>
    <tr><td class='k'>Receipt Number</td><td><b>{pa.get('receipt', 'EAC0000000000')}</b></td></tr>
    <tr><td class='k'>Notice Type</td><td>Approval Notice</td></tr>
    <tr><td class='k'>Class</td><td>H-1B — Specialty Occupation</td></tr>
    <tr><td class='k'>Petitioner</td><td>{pa.get('prior_employer', 'Prior Employer, Inc.')}</td></tr>
    <tr><td class='k'>Beneficiary</td><td>{p['surname'].upper()}, {p['given'].upper()}</td></tr>
    <tr><td class='k'>Valid From / To</td><td>{long_date('2023-03-01')} &ndash; {long_date('2026-02-28')}</td></tr>
    <tr><td class='k'>Petition Validity</td><td>Approved — prior employment authorized</td></tr>
  </table>
  <p>This prior approval establishes the beneficiary's H-1B status and is provided to support
     portability for the new petition.</p>
  <p class='stamp'>APPROVED &middot; PRIOR PETITION</p>""")


def paystub_html(p: dict) -> str:  # recent pay stub from current payer
    payer = _current_payer(p)
    gross = round(p["annual_wage_usd"] / 24)         # semi-monthly
    fed = round(gross * 0.16); fica = round(gross * 0.0765)
    state = round(gross * 0.04); net = gross - fed - fica - state
    return page(f"""
  <h1>Earnings Statement</h1>
  <p class='meta'>{payer} &middot; Payroll &middot; Confidential</p><hr>
  <table>
    <tr><td class='k'>Employee</td><td>{p['given'].title()} {p['surname'].title()}</td></tr>
    <tr><td class='k'>Pay Period</td><td>{long_date('2026-05-16')} &ndash; {long_date('2026-05-31')}</td></tr>
    <tr><td class='k'>Pay Date</td><td>{long_date('2026-06-05')}</td></tr>
    <tr><td class='k'>Pay Type</td><td>Salary (semi-monthly)</td></tr>
    <tr><td class='k'>Gross Pay</td><td><b>${gross:,}</b></td></tr>
    <tr><td class='k'>Federal Tax</td><td>-${fed:,}</td></tr>
    <tr><td class='k'>Social Security + Medicare</td><td>-${fica:,}</td></tr>
    <tr><td class='k'>State Tax</td><td>-${state:,}</td></tr>
    <tr><td class='k'>Net Pay</td><td><b>${net:,}</b></td></tr>
  </table>
  <p class='meta'>YTD gross ${round(p['annual_wage_usd'] * 0.42):,}. Synthetic — not a real wage record.</p>""")


def transcript_html(p: dict) -> str:  # academic transcript (abigail's foreign transcript)
    d = p["degree"]
    field = d["field"]
    courses = [
        ("Engineering Mathematics", "A"), ("Mechanics of Materials", "A-"),
        ("Thermodynamics", "B+"), (f"{field} Design I", "A"),
        (f"{field} Design II", "A-"), ("Finite Element Analysis", "A"),
        ("Fluid Dynamics", "B+"), ("Capstone Project", "A"),
    ]
    rows = "".join(f"<tr><td class='k'>{c}</td><td>{g}</td></tr>" for c, g in courses)
    inst = d.get("institution", "University")
    return page(f"""
  <h1>Official Academic Transcript</h1>
  <p class='meta'>{inst} &middot; Office of the Registrar</p><hr>
  <p>Student: <b>{p['given'].title()} {p['surname'].title()}</b> &middot;
     Program: {d.get('original', d['us_equivalent'])} ({field}) &middot;
     Year awarded: {d.get('year', d.get('conferred', ''))}</p>
  <table>{rows}
    <tr><td class='k'><b>Cumulative GPA</b></td><td><b>3.7 / 4.0</b></td></tr>
  </table>
  <p class='stamp'>OFFICIAL TRANSCRIPT</p>""")


def tn_approval_html(p: dict) -> str:  # prior TN admission record (abigail)
    return page(f"""
  <h1>Form I-94 — TN Admission Record (Prior Status)</h1>
  <p class='meta'>U.S. Customs and Border Protection &middot; Prior Nonimmigrant Admission</p><hr>
  <table>
    <tr><td class='k'>I-94 Number</td><td><b>{_synth_id(p, '', 11)}</b></td></tr>
    <tr><td class='k'>Name</td><td>{p['surname'].upper()}, {p['given'].upper()}</td></tr>
    <tr><td class='k'>Class of Admission</td><td><b>TN</b> (USMCA Professional)</td></tr>
    <tr><td class='k'>Profession</td><td>Engineer</td></tr>
    <tr><td class='k'>Admit Until Date</td><td>{p.get('i94_admit_until', '2026-12-31')}</td></tr>
    <tr><td class='k'>Country of Citizenship</td><td>{p['nationality_long']}</td></tr>
  </table>
  <p>Provided to evidence the beneficiary's current TN status preceding the H-1B change of status.</p>""")


# extra-doc dispatch: key → (renderer, human label for ground-truth)
EXTRA_RENDERERS = {
    "resume": resume_html,
    "i20": i20_html,
    "i797-prior": i797_prior_html,
    "paystub": paystub_html,
    "transcript": transcript_html,
    "tn-approval": tn_approval_html,
}
EXTRA_LABELS = {
    "resume": "Candidate résumé / CV (2 pages; over-shared, not required for I-129)",
    "i20": "Form I-20 / OPT student record (status history, not required)",
    "i797-prior": "Prior I-797C H-1B approval notice (supports portability, not required)",
    "paystub": "Recent pay stub from current employer (over-shared, not required)",
    "transcript": "Academic transcript (over-shared alongside the degree, not required)",
    "tn-approval": "Prior TN admission record (status history, not required)",
}


# ── profiles ─────────────────────────────────────────────────────────────────
PROFILES = [
    {
        "slug": "arjun-kumar", "surname": "KUMAR", "given": "ARJUN", "real_passport": True,
        "nationality": "IND", "nationality_long": "India", "country_of_birth": "IND",
        "sex": "M", "dob": "1985-05-24", "place_of_birth": "Mumbai, India",
        "passport_number": "P8401723", "passport_issue": "2021-06-15", "passport_expiration": "2031-06-14",
        "current_nonimmigrant_status": "F-1", "i94_number": "12345678901",
        "i94_entry_date": "2022-08-18", "i94_admit_until": "D/S (F-1 duration of status)",
        "us_physical_address": "1200 W Dean Keeton St, Apt 305, Austin, TX 78705",
        "job_title": "Senior Data Scientist", "soc_code": "15-2051",
        "annual_wage_usd": 142000, "prevailing_wage": 131019,
        "requested_start_date": "2026-10-01", "requested_end_date": "2029-09-30",
        "lca_case_number": "I-200-26273-558041",
        "degree_min": "Master's degree", "degree_field": "Computer Science",
        "specialty_basis": "The role's data-modeling and statistical-inference duties are of such complexity that they are associated with attainment of at least a master's degree in the field.",
        "degree": {"us_equivalent": "Master of Science", "field": "Computer Science",
                   "institution": "The University of Texas at Austin", "conferred": "2024-05-18"},
        "employer": {"name": "Northwind Analytics, Inc.", "ein": "47-3829150",
                     "address": "500 Technology Drive, Suite 400, Austin, TX 78701",
                     "signer": "Daniel Okafor", "signer_title": "VP, People Operations"},
        "worksite_address": "500 Technology Drive, Suite 400, Austin, TX 78701",
        "extras": ["resume", "i20", "paystub"],
        "scenario": "Cap-subject new hire; F-1 OPT to H-1B; US STEM master's.",
        "material_change": {
            "type": "compensation",
            "subject": "Updated compensation for Arjun Kumar H-1B petition",
            "body": "Hi — following our comp review, Arjun Kumar's annualized base salary for the Senior Data Scientist role has been increased from $142,000 to $156,000 USD, effective on his petition start date. Please make sure the petition reflects the new figure. Thanks, Daniel Okafor, Northwind Analytics.",
            "changed": {"annual_wage_usd": 156000},
        },
    },
    {
        "slug": "yangben-zhengjian", "surname": "ZHENGJIAN", "given": "YANGBEN", "real_passport": True,
        "nationality": "CHN", "nationality_long": "China", "country_of_birth": "CHN",
        "sex": "F", "dob": "1985-03-20", "place_of_birth": "Guangzhou, China",
        "passport_number": "EF1260892", "passport_issue": "2019-01-18", "passport_expiration": "2029-01-17",
        "current_nonimmigrant_status": "H-1B", "i94_number": "98765432100",
        "i94_entry_date": "2023-03-04", "i94_admit_until": "2027-02-28",
        "us_physical_address": "815 Pine St, Apt 1102, Seattle, WA 98101",
        "job_title": "Data Engineer", "soc_code": "15-1243",
        "annual_wage_usd": 138000, "prevailing_wage": 129355,
        "requested_start_date": "2026-11-01", "requested_end_date": "2029-10-31",
        "lca_case_number": "I-200-26288-771902",
        "degree_min": "Master's degree", "degree_field": "Computer Engineering",
        "specialty_basis": "The data-pipeline architecture and distributed-systems duties require specialized knowledge attained through a master's degree in computer engineering or a closely related field.",
        "degree": {"us_equivalent": "Master of Science", "field": "Computer Engineering",
                   "institution": "Carnegie Mellon University", "conferred": "2017-12-15"},
        "employer": {"name": "Cascade Robotics, LLC", "ein": "84-2910736",
                     "address": "2200 6th Avenue, Seattle, WA 98121",
                     "signer": "Marta Ruiz", "signer_title": "Director of Talent"},
        "worksite_address": "2200 6th Avenue, Seattle, WA 98121",
        "prior_approval": {"receipt": "EAC2590012345", "prior_employer": "Meridian Software Corp"},
        "extras": ["resume", "i797-prior", "paystub"],
        "scenario": "H-1B transfer / portability (currently in H-1B with another employer).",
        "material_change": {
            "type": "worksite",
            "subject": "Office relocation — Yangben Zhengjian worksite change",
            "body": "Heads up: Cascade Robotics is relocating the engineering team. Yangben Zhengjian's primary worksite will move from 2200 6th Avenue, Seattle, WA 98121 to 10500 NE 8th Street, Suite 1400, Bellevue, WA 98004, effective the first month of employment. Let me know what we need for the petition. — Marta Ruiz, Cascade Robotics.",
            "changed": {"worksite_address": "10500 NE 8th Street, Suite 1400, Bellevue, WA 98004"},
        },
    },
    {
        "slug": "abigail-medina", "surname": "MEDINA PEREZ", "given": "ABIGAIL", "real_passport": True,
        "nationality": "MEX", "nationality_long": "Mexico", "country_of_birth": "MEX",
        "sex": "F", "dob": "1981-01-17", "place_of_birth": "Ciudad de Mexico, Mexico",
        "passport_number": "G14820073", "passport_issue": "2022-06-12", "passport_expiration": "2032-06-11",
        "current_nonimmigrant_status": "TN", "i94_number": "55512340987",
        "i94_entry_date": "2024-01-22", "i94_admit_until": "2026-12-31",
        "us_physical_address": "4120 Woodward Ave, Apt 7B, Detroit, MI 48201",
        "job_title": "Mechanical Engineer", "soc_code": "17-2141",
        "annual_wage_usd": 108000, "prevailing_wage": 101733,
        "requested_start_date": "2026-10-15", "requested_end_date": "2029-10-14",
        "lca_case_number": "I-200-26259-440318",
        "degree_min": "Bachelor's degree", "degree_field": "Mechanical Engineering",
        "specialty_basis": "Mechanical-design and FEA duties require the application of engineering principles attained through at least a bachelor's degree in mechanical engineering.",
        "degree": {"foreign": True,
                   "original": "Licenciatura en Ingenieria Mecanica",
                   "institution": "Universidad Nacional Autonoma de Mexico (UNAM)",
                   "year": "2003", "evaluator": "Global Credential Evaluators, Inc.",
                   "us_equivalent": "Bachelor of Science", "field": "Mechanical Engineering"},
        "employer": {"name": "BrightForge Manufacturing Co.", "ein": "91-3047821",
                     "address": "1400 Rosa Parks Blvd, Detroit, MI 48216",
                     "signer": "Karen Whitfield", "signer_title": "Director of Engineering"},
        "worksite_address": "1400 Rosa Parks Blvd, Detroit, MI 48216",
        "extras": ["resume", "transcript", "tn-approval"],
        "scenario": "Foreign degree + credential evaluation; TN to H-1B.",
        "material_change": {
            "type": "job_title",
            "subject": "Promotion / role change — Abigail Medina-Perez",
            "body": "Quick update before filing: Abigail Medina-Perez is being promoted from Mechanical Engineer to Senior Mechanical Engineer, taking on design-lead responsibilities for our drivetrain program. Her base salary stays at $108,000. Does the higher-level title change anything for the H-1B? — Karen Whitfield, BrightForge.",
            "changed": {"job_title": "Senior Mechanical Engineer"},
        },
    },
]


def ground_truth(p: dict) -> dict:
    gt = {
        "_note": "Expected extraction values for the Pearson H-1B demo accuracy check. Fictional / synthetic — no real PII.",
        "scenario": p["scenario"],
        "persona": p["slug"],
        "beneficiary_from_passport": {
            "beneficiary_full_name": f"{p['given']} {p['surname']}",
            "beneficiary_dob": p["dob"],
            "beneficiary_country_of_citizenship": p["nationality"],
            "passport_number": p["passport_number"].upper(),
            "passport_expiration": p["passport_expiration"],
        },
        "employment_from_offer_letter": {
            "petitioner_legal_name": p["employer"]["name"],
            "petitioner_ein": p["employer"]["ein"],
            "petitioner_address": p["employer"]["address"],
            "job_title": p["job_title"],
            "soc_code": p["soc_code"],
            "annual_wage_usd": p["annual_wage_usd"],
            "worksite_address": p["worksite_address"],
            "requested_start_date": p["requested_start_date"],
            "requested_end_date": p["requested_end_date"],
            "requested_status": "H-1B",
        },
        "status_from_i94": {
            "i94_number": p["i94_number"],
            "current_nonimmigrant_status": p["current_nonimmigrant_status"],
        },
        "education_from_degree": {
            "beneficiary_degree": p["degree"]["us_equivalent"],
            "degree_field": p["degree"]["field"],
        },
        "mrz": {"line1": p["_mrz"][0], "line2": p["_mrz"][1]},
        "material_change_email": p["material_change"],
    }
    if p.get("extras"):
        gt["extra_documents"] = [
            {"file": f"{n}.pdf", "kind": n, "required": False,
             "description": EXTRA_LABELS.get(n, n)}
            for n in p["extras"]
        ]
    if p.get("dependents"):
        gt["dependents"] = p["dependents"]
    if p.get("prior_approval"):
        gt["prior_approval"] = p["prior_approval"]
    return gt


def html_to_pdf(htmls, outdir: str):
    profile = f"file://{outdir}/.soffice-profile"
    subprocess.run(
        ["soffice", "--headless", f"-env:UserInstallation={profile}",
         "--convert-to", "pdf", "--outdir", outdir, *htmls],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def write_and_render(d: str, docs: dict):
    """Write each document's HTML into ``<d>/_src/`` (the editable render *source* —
    NOT a client artifact) and render the PDF into ``<d>`` (the case folder). This
    keeps the case folder an honest picture of a client packet — only the PDFs +
    images a client would actually hand over — while the HTML stays versioned and
    diffable under ``_src/`` so the corpus regenerates without LibreOffice.
    """
    src = os.path.join(d, "_src")
    os.makedirs(src, exist_ok=True)
    html_paths = []
    for name, html in docs.items():
        hp = os.path.join(src, f"{name}.html")
        with open(hp, "w") as f:
            f.write(html)
        html_paths.append(hp)
    html_to_pdf(html_paths, d)


# ── ADVERSARIAL (negative) tier ──────────────────────────────────────────────
# Each case = a clone of a happy-path base profile + exactly ONE injected defect.
# `field_overrides` apply to every document (a global/internal defect); `doc_overrides`
# apply per-document, so a field can DIFFER across docs (a cross-document
# contradiction — the product's real moat). `mrz_corrupt` flips one MRZ check digit
# AFTER a valid MRZ is built (detectable only by re-running the ICAO 9303 algorithm).
#
# `expected_gates` is the SPEC, not just a label: a case PASSES only when the named
# gate fires (the right gate must fire). Most of these gates
# are the executable spec for the
# cross-document validation layer (the differentiator vs extraction-only incumbents).
# The `mrz_checkdigit_corrupt` gate is detected via MRZ check-digit validation.
DOC_NAMES = ["passport", "offer", "lca", "i94", "degree", "support-letter"]

ADVERSARIAL = [
    {
        "slug": "wage-below-prevailing", "base": "arjun-kumar",
        "defect": "wage_below_prevailing",
        # offered wage drops below the LCA prevailing wage (131,019). Both offer and
        # LCA read the same field, so the offer corroborates the LCA's own breach.
        "field_overrides": {"annual_wage_usd": 120000},
        "expected_gates": [{
            "gate": "wage_below_prevailing", "category": "wage-compliance",
            "detects": "offered annual wage ($120,000) is below the certified LCA prevailing wage ($131,019)",
            "documents": ["offer", "lca"], "cross_document": True, "severity": "denial",
            "affected_form": "I-129 Part 5 + LCA",
            "why": "The offered wage must meet or exceed the prevailing wage (20 CFR 655.731); below-prevailing is a statutory violation and a denial ground.",
            "evidence": {"annual_wage_usd": 120000, "prevailing_wage": 131019},
        }],
    },
    {
        "slug": "identity-name-mismatch", "base": "arjun-kumar",
        "defect": "identity_name_mismatch",
        # Employer-generated docs (offer, support letter) carry a typo'd surname;
        # the passport + I-94 (government docs) keep the correct one.
        "doc_overrides": {"offer": {"surname": "KUMARR"},
                          "support-letter": {"surname": "KUMARR"}},
        "expected_gates": [{
            "gate": "identity_name_mismatch", "category": "identity-consistency",
            "detects": "beneficiary surname on the offer/support letter ('KUMARR') does not match the passport/I-94 ('KUMAR')",
            "documents": ["passport", "offer", "i94"], "cross_document": True, "severity": "rfe",
            "affected_form": "I-129 Part 3",
            "why": "Biographic data must match across the petition and ALL supporting documents; a silent inconsistency draws an RFE or fraud concern.",
            "evidence": {"passport_surname": "KUMAR", "offer_surname": "KUMARR"},
        }],
    },
    {
        "slug": "soc-code-mismatch", "base": "yangben-zhengjian",
        "defect": "soc_code_mismatch",
        # LCA certifies a different SOC than the offer/petition occupation.
        "doc_overrides": {"lca": {"soc_code": "15-1252"}},
        "expected_gates": [{
            "gate": "soc_code_mismatch", "category": "lca-correspondence",
            "detects": "SOC code on the LCA (15-1252) does not correspond to the offer/petition occupation (15-1243)",
            "documents": ["offer", "lca"], "cross_document": True, "severity": "rfe",
            "affected_form": "I-129 + LCA",
            "why": "The LCA must correspond to the petition; SOC misclassification is a leading RFE/denial cause.",
            "evidence": {"offer_soc_code": "15-1243", "lca_soc_code": "15-1252"},
        }],
    },
    {
        "slug": "worksite-outside-lca-area", "base": "yangben-zhengjian",
        "defect": "worksite_outside_lca_area",
        # Offer/petition worksite is in a different metro than the LCA-certified area.
        "doc_overrides": {"offer": {"worksite_address": "1300 SW 5th Avenue, Suite 2000, Portland, OR 97201"}},
        "expected_gates": [{
            "gate": "worksite_outside_lca_area", "category": "lca-correspondence",
            "detects": "petition worksite (Portland, OR) is outside the area of intended employment certified on the LCA (Seattle, WA)",
            "documents": ["offer", "lca"], "cross_document": True, "severity": "rfe",
            "affected_form": "LCA + I-129 Part 5",
            "why": "A worksite outside the certified area requires a new LCA + amended petition (Matter of Simeio Solutions).",
            "evidence": {"offer_worksite": "Portland, OR 97201", "lca_worksite": "Seattle, WA 98121"},
        }],
    },
    {
        "slug": "passport-expired-before-period", "base": "abigail-medina",
        "defect": "passport_expired_before_period",
        # Passport expires before the requested employment period even begins.
        "field_overrides": {"passport_issue": "2016-10-01", "passport_expiration": "2026-09-30"},
        "expected_gates": [{
            "gate": "passport_expired_before_period", "category": "passport-validity",
            "detects": "passport expires 2026-09-30, before the requested employment period (2026-10-15 → 2029-10-14)",
            "documents": ["passport"], "cross_document": False, "severity": "blocker",
            "affected_form": "passport",
            "why": "An expired/expiring passport blocks admissibility and consular processing for the requested period.",
            "evidence": {"passport_expiration": "2026-09-30", "requested_start_date": "2026-10-15"},
        }],
    },
    {
        "slug": "mrz-checkdigit-corrupt", "base": "arjun-kumar",
        "defect": "mrz_checkdigit_corrupt",
        # A valid MRZ is built, then the passport-number check digit (line2[9]) is
        # flipped — the only deterministically-detectable defect here. mrtd rejects it.
        "mrz_corrupt": True,
        "expected_gates": [{
            "gate": "mrz_checkdigit_corrupt", "category": "document-integrity",
            "detects": "passport MRZ line 2 fails the ICAO 9303 passport-number check digit; beneficiary identity facts cannot be deterministically validated",
            "documents": ["passport"], "cross_document": False, "severity": "rfe",
            "affected_form": "I-129 Part 3",
            "why": "A failed check digit means OCR error or tampering. mrtd rejects the MRZ → facts are withheld; surface an mrz-validation review gate instead of silently dropping identity.",
            "evidence": {"corrupted_field": "passport_number_check_digit", "line2_index": 9},
        }],
    },
    {
        "slug": "employer-name-mismatch", "base": "arjun-kumar",
        "defect": "employer_name_mismatch",
        # The certified LCA names a different legal entity than the offer letter —
        # "Northwind Analytics, Inc." (offer) vs "Northwind Analytics LLC" (LCA). Same
        # EIN + address, so it is a genuine entity-type divergence (Inc vs LLC), NOT a
        # punctuation/casing artifact — the case that company-name normalization must STILL catch.
        "doc_overrides": {"lca": {"employer": {
            "name": "Northwind Analytics LLC", "ein": "47-3829150",
            "address": "500 Technology Drive, Suite 400, Austin, TX 78701",
            "signer": "Daniel Okafor", "signer_title": "VP, People Operations"}}},
        "expected_gates": [{
            "gate": "employer_name_mismatch", "category": "petitioner-consistency",
            "detects": "petitioner legal name on the LCA ('Northwind Analytics LLC') does not match the offer letter ('Northwind Analytics, Inc.')",
            "documents": ["offer", "lca"], "cross_document": True, "severity": "rfe",
            "affected_form": "I-129 Part 1 + LCA",
            "why": "The petitioner must be the same legal entity across the petition, offer, and LCA; an entity-name divergence signals a successor-in-interest question or a filing error and draws an RFE.",
            "evidence": {"offer_petitioner_legal_name": "Northwind Analytics, Inc.",
                         "lca_petitioner_legal_name": "Northwind Analytics LLC"},
        }],
    },
    {
        "slug": "employer-ein-mismatch", "base": "yangben-zhengjian",
        "defect": "employer_ein_mismatch",
        # The certified LCA carries a different FEIN than the offer letter, same legal
        # name — a different legal entity (successor-in-interest) or a transposed EIN.
        # Compared digit-only, so it is a real divergence, not a formatting artifact.
        "doc_overrides": {"lca": {"employer": {
            "name": "Cascade Robotics, LLC", "ein": "82-7654321",
            "address": "2200 6th Avenue, Seattle, WA 98121",
            "signer": "Marta Ruiz", "signer_title": "Director of Talent"}}},
        "expected_gates": [{
            "gate": "employer_ein_mismatch", "category": "petitioner-consistency",
            "detects": "petitioner FEIN on the LCA (82-7654321) does not match the offer letter (84-2910736)",
            "documents": ["offer", "lca"], "cross_document": True, "severity": "rfe",
            "affected_form": "I-129 Part 1 + LCA",
            "why": "A different FEIN generally signals a different legal entity; the petitioner on the LCA must be the petitioner on the I-129. A mismatch is a successor-in-interest / wrong-entity RFE.",
            "evidence": {"offer_petitioner_ein": "84-2910736",
                         "lca_petitioner_ein": "82-7654321"},
        }],
    },
]


def _doc_view(base: dict, field_ov: dict, doc_ov: dict, doc: str) -> dict:
    """A per-document copy of the base profile with global + per-doc overrides applied."""
    v = copy.deepcopy(base)
    v.update(field_ov)
    v.update(doc_ov.get(doc, {}))
    return v


def adv_ground_truth(views: dict, case: dict) -> dict:
    """Ground truth for an adversarial case: what EACH document actually says (sourced
    from its own view, so a cross-doc contradiction is represented faithfully) + the
    injected defect + the expected gate(s)."""
    pv, ov, iv, dv = views["passport"], views["offer"], views["i94"], views["degree"]
    gt = {
        "_note": "ADVERSARIAL fixture for the Pearson H-1B intake validation suite. One injected "
                 "defect per case. Fictional / synthetic — no real PII. A case PASSES only "
                 "when the named expected gate fires (not merely 'some' gate).",
        "defect": case["defect"],
        "base_persona": case["base"],
        "scenario": pv["scenario"],
        "beneficiary_from_passport": {
            "beneficiary_full_name": f"{pv['given']} {pv['surname']}",
            "beneficiary_dob": pv["dob"],
            "beneficiary_country_of_citizenship": pv["nationality"],
            "passport_number": pv["passport_number"].upper(),
            "passport_expiration": pv["passport_expiration"],
        },
        "employment_from_offer_letter": {
            "petitioner_legal_name": ov["employer"]["name"],
            "petitioner_ein": ov["employer"]["ein"],
            "job_title": ov["job_title"],
            "soc_code": ov["soc_code"],
            "annual_wage_usd": ov["annual_wage_usd"],
            "worksite_address": ov["worksite_address"],
            "requested_start_date": ov["requested_start_date"],
            "requested_end_date": ov["requested_end_date"],
        },
        "status_from_i94": {
            "i94_number": iv["i94_number"],
            "current_nonimmigrant_status": iv["current_nonimmigrant_status"],
        },
        "education_from_degree": {
            "beneficiary_degree": dv["degree"]["us_equivalent"],
            "degree_field": dv["degree"]["field"],
        },
        "mrz": {"line1": pv["_mrz"][0], "line2": pv["_mrz"][1]},
        "expected_gates": case["expected_gates"],
    }
    if case.get("mrz_corrupt"):
        gt["mrz"]["corrupted"] = True
        gt["mrz"]["corrupted_index"] = 9
        gt["mrz"]["note"] = "line2[9] (passport-number check digit) flipped; the visual zone is correct."
    return gt


def build_adversarial():
    os.makedirs(ADV_OUT_ROOT, exist_ok=True)
    by_slug = {p["slug"]: p for p in PROFILES}
    print(f"\n=== adversarial tier ({len(ADVERSARIAL)} cases) ===")
    for case in ADVERSARIAL:
        base = by_slug[case["base"]]
        field_ov = case.get("field_overrides", {})
        doc_ov = case.get("doc_overrides", {})
        slug = case["slug"]
        d = os.path.join(ADV_OUT_ROOT, slug)
        os.makedirs(d, exist_ok=True)

        views = {name: _doc_view(base, field_ov, doc_ov, name) for name in DOC_NAMES}
        # The passport (government ID) is authoritative; its MRZ is built from its own view.
        views["passport"]["_mrz"] = build_mrz(views["passport"])
        if case.get("mrz_corrupt"):
            l1, l2 = views["passport"]["_mrz"]
            i = 9  # passport-number check digit
            l2 = l2[:i] + str((int(l2[i]) + 1) % 10) + l2[i + 1:]
            assert len(l2) == 44
            views["passport"]["_mrz"] = (l1, l2)

        # Passport image: a person has ONE passport. When the base case has a sourced
        # real passport AND this defect does NOT alter the passport itself, reuse the
        # blessed image (accurate + high quality). Only cases that change the passport
        # (expiry / corrupt MRZ) render a synthetic SPECIMEN that shows the defect —
        # those get an edited real-image variant in a follow-on (see SOURCING notes).
        alters_pp = (case.get("mrz_corrupt")
                     or "passport_expiration" in field_ov
                     or "passport" in doc_ov)
        base_pp = os.path.join(OUT_ROOT, case["base"], "passport.png")
        if base.get("real_passport") and not alters_pp and os.path.exists(base_pp):
            shutil.copy(base_pp, os.path.join(d, "passport.png"))
        else:
            render_passport(views["passport"], os.path.join(d, "passport.png"))

        renderers = {"offer": offer_html, "lca": lca_html, "i94": i94_html,
                     "degree": degree_html, "support-letter": support_html}
        write_and_render(d, {name: fn(views[name]) for name, fn in renderers.items()})

        with open(os.path.join(d, "ground-truth.json"), "w") as f:
            json.dump(adv_ground_truth(views, case), f, indent=2, ensure_ascii=False)
        print(f"  {slug:30s} defect={case['defect']}")
    print(f"wrote {len(ADVERSARIAL)} adversarial cases under {ADV_OUT_ROOT}")


# ── INCOMPLETE ('not-enough') tier ───────────────────────────────────────────
# The mirror of the adversarial tier: instead of a CONTRADICTION, exactly one
# REQUIRED document is absent, or present but missing its key field. A real client
# forgets things. Proves the completeness gates (validate::validate_completeness):
#   missing_required_document (blocker) · missing_required_field (rfe).
# `omit_doc` drops a whole document; `blank_field` keeps the document but removes the
# field (the offer is rendered with no salary via offer_html's `_omit_wage`).
INCOMPLETE = [
    {
        "slug": "missing-lca", "base": "yangben-zhengjian",
        "defect": "missing_required_document", "omit_doc": "lca",
        "expected_gates": [{
            "gate": "missing_required_document", "category": "intake-completeness",
            "missing_kind": "lca", "severity": "blocker",
            "detects": "no certified LCA (ETA-9035) in the packet — prevailing wage, SOC, and worksite cannot be verified and the I-129 cannot be filed",
            "affected_form": "LCA + I-129 Part 5",
            "why": "A certified LCA is a statutory prerequisite to filing the H-1B petition (INA 212(n)).",
        }],
    },
    {
        "slug": "missing-degree", "base": "abigail-medina",
        "defect": "missing_required_document", "omit_doc": "degree",
        "expected_gates": [{
            "gate": "missing_required_document", "category": "intake-completeness",
            "missing_kind": "degree", "severity": "blocker",
            "detects": "no degree / credential evaluation in the packet — the specialty-occupation requirement and the beneficiary's qualification cannot be established",
            "affected_form": "I-129 specialty-occupation evidence",
            "why": "An H-1B specialty occupation requires evidence the beneficiary holds the required degree (8 CFR 214.2(h)).",
        }],
    },
    {
        "slug": "missing-i94", "base": "arjun-kumar",
        "defect": "missing_required_document", "omit_doc": "i94",
        "expected_gates": [{
            "gate": "missing_required_document", "category": "intake-completeness",
            "missing_kind": "i94", "severity": "blocker",
            "detects": "no I-94 record in the packet — current nonimmigrant status and change-of-status eligibility cannot be verified",
            "affected_form": "I-129 Part 2",
            "why": "The I-94 establishes the beneficiary's current status and admission period, required for the change/extension of status request.",
        }],
    },
    {
        "slug": "missing-wage", "base": "arjun-kumar",
        "defect": "missing_required_field", "blank_field": {"doc": "offer", "field": "annual_wage_usd"},
        "expected_gates": [{
            "gate": "missing_required_field", "category": "intake-completeness",
            "missing_field": "annual_wage_usd", "severity": "rfe",
            "detects": "the offer letter is present but states no annualized salary — the offered wage cannot be read or compared to the prevailing wage",
            "affected_form": "I-129 Part 5",
            "why": "The offered wage is a required field (and must be checked against the prevailing wage); an offer with no salary is an incomplete intake.",
        }],
    },
]

# the key facts each present document contributes (predicate, value, source_kind)
REQ_KINDS = ["passport", "offer", "lca", "i94", "degree"]


def _present_facts(p: dict, present: list, omit_wage: bool) -> list:
    facts = []

    def add(pred, val, kind):
        facts.append({"predicate": pred, "value": val, "source_kind": kind})

    name = f"{p['given']} {p['surname']}"
    if "passport" in present:
        add("passport_number", p["passport_number"].upper(), "passport")
        add("beneficiary_full_name", name, "passport")
        add("passport_expiration", p["passport_expiration"], "passport")
    if "offer" in present:
        if not omit_wage:
            add("annual_wage_usd", p["annual_wage_usd"], "offer")
        add("soc_code", p["soc_code"], "offer")
        add("job_title", p["job_title"], "offer")
        add("worksite_address", p["worksite_address"], "offer")
        add("requested_start_date", p["requested_start_date"], "offer")
        add("beneficiary_full_name", name, "offer")
    if "lca" in present:
        add("prevailing_wage", p["prevailing_wage"], "lca")
        add("soc_code", p["soc_code"], "lca")
        add("worksite_address", p["worksite_address"], "lca")
    if "i94" in present:
        add("current_nonimmigrant_status", p["current_nonimmigrant_status"], "i94")
        add("i94_number", p["i94_number"], "i94")
    if "degree" in present:
        add("beneficiary_degree", p["degree"]["us_equivalent"], "degree")
        add("degree_field", p["degree"]["field"], "degree")
    return facts


def incomplete_ground_truth(p: dict, case: dict, present: list, omit_wage: bool) -> dict:
    req_present = [k for k in REQ_KINDS if k in present]
    missing_note = case.get("omit_doc") or f"{case.get('blank_field', {}).get('field', 'field')} (field)"
    return {
        "_note": "INCOMPLETE ('not-enough') fixture for the Pearson H-1B intake-completeness suite. "
                 "Exactly one required document or field is MISSING. Fictional / synthetic — no "
                 "real PII. A case PASSES only when the named completeness gate fires.",
        "defect": case["defect"],
        "base_persona": case["base"],
        "scenario": f"{p['scenario']}  (intake incomplete — missing {missing_note})",
        "documents_present": req_present,
        "documents_missing": [case["omit_doc"]] if case.get("omit_doc") else [],
        "facts": _present_facts(p, present, omit_wage),
        "expected_gates": case["expected_gates"],
    }


def build_incomplete():
    os.makedirs(INC_OUT_ROOT, exist_ok=True)
    by_slug = {p["slug"]: p for p in PROFILES}
    print(f"\n=== incomplete tier ({len(INCOMPLETE)} cases) ===")
    for case in INCOMPLETE:
        base = by_slug[case["base"]]
        p = copy.deepcopy(base)
        p.pop("extras", None)  # the incomplete tier is about the REQUIRED packet, no over-share
        p["_mrz"] = build_mrz(p)
        omit = case.get("omit_doc")
        omit_wage = case.get("blank_field", {}).get("field") == "annual_wage_usd"
        if omit_wage:
            p["_omit_wage"] = True
        present = [k for k in DOC_NAMES if k != omit]  # DOC_NAMES incl. support-letter

        slug = case["slug"]
        d = os.path.join(INC_OUT_ROOT, slug)
        os.makedirs(d, exist_ok=True)

        # passport: reuse the blessed real image unless the passport itself is omitted
        if "passport" in present:
            base_pp = os.path.join(OUT_ROOT, case["base"], "passport.png")
            if base.get("real_passport") and os.path.exists(base_pp):
                shutil.copy(base_pp, os.path.join(d, "passport.png"))
            else:
                render_passport(p, os.path.join(d, "passport.png"))

        renderers = {"offer": offer_html, "lca": lca_html, "i94": i94_html,
                     "degree": degree_html, "support-letter": support_html}
        docs = {name: renderers[name](p) for name in present if name in renderers}
        write_and_render(d, docs)

        with open(os.path.join(d, "ground-truth.json"), "w") as f:
            json.dump(incomplete_ground_truth(p, case, present, omit_wage), f,
                      indent=2, ensure_ascii=False)
        miss = omit or case.get("blank_field")
        print(f"  {slug:24s} defect={case['defect']} missing={miss}")
    print(f"wrote {len(INCOMPLETE)} incomplete cases under {INC_OUT_ROOT}")


def main():
    # `--adversarial-only` skips the happy-path regen (whose PDFs/PNGs carry render
    # timestamps and would otherwise show as spuriously modified in git).
    # `--extras-only` renders ONLY the over-shared 'too-much' docs into existing case
    # dirs + rewrites ground-truth — it never touches the required PDFs or the sourced
    # passports, keeping the git diff to just the new extra docs.
    adversarial_only = "--adversarial-only" in sys.argv
    incomplete_only = "--incomplete-only" in sys.argv
    extras_only = "--extras-only" in sys.argv
    # `--offers-only` re-renders ONLY offer.pdf + _src/offer.html across every tier —
    # surgical (no spurious all-PDF timestamp churn) after an offer_html template change.
    offers_only = "--offers-only" in sys.argv
    print(f"fonts: sans={os.path.basename(SANS)} mono={os.path.basename(MONO)} "
          f"deva={os.path.basename(DEVA)} cjk={os.path.basename(CJK)}")
    if adversarial_only:
        for p in PROFILES:  # MRZ needed by the adversarial bases
            p["_mrz"] = build_mrz(p)
        build_adversarial()
        return
    if incomplete_only:
        for p in PROFILES:  # MRZ needed by the incomplete bases
            p["_mrz"] = build_mrz(p)
        build_incomplete()
        return
    if extras_only:
        print("\n=== extras-only (over-shared 'too-much' docs) ===")
        for p in PROFILES:
            p["_mrz"] = build_mrz(p)  # ground_truth() references the MRZ
            d = os.path.join(OUT_ROOT, p["slug"])
            if not os.path.isdir(d):
                print(f"  skip {p['slug']} (no case dir)")
                continue
            extras = {n: EXTRA_RENDERERS[n](p) for n in p.get("extras", [])}
            if extras:
                write_and_render(d, extras)
            with open(os.path.join(d, "ground-truth.json"), "w") as f:
                json.dump(ground_truth(p), f, indent=2, ensure_ascii=False)
            print(f"  {p['slug']:20s} +{len(extras)} extras "
                  f"({', '.join(extras)}) · ground-truth rewritten")
        return
    if offers_only:
        print("\n=== offers-only (re-render offer.pdf + _src/offer.html) ===")
        by_slug = {p["slug"]: p for p in PROFILES}
        n = 0
        for p in PROFILES:  # happy tier
            d = os.path.join(OUT_ROOT, p["slug"])
            if os.path.isdir(d):
                write_and_render(d, {"offer": offer_html(p)})
                n += 1
        for case in ADVERSARIAL:  # adversarial tier (per-doc views with overrides)
            d = os.path.join(ADV_OUT_ROOT, case["slug"])
            if not os.path.isdir(d):
                continue
            ov = _doc_view(by_slug[case["base"]], case.get("field_overrides", {}),
                           case.get("doc_overrides", {}), "offer")
            write_and_render(d, {"offer": offer_html(ov)})
            n += 1
        for case in INCOMPLETE:  # incomplete tier
            d = os.path.join(INC_OUT_ROOT, case["slug"])
            if not os.path.isdir(d) or case.get("omit_doc") == "offer":
                continue
            p = copy.deepcopy(by_slug[case["base"]])
            if case.get("blank_field", {}).get("field") == "annual_wage_usd":
                p["_omit_wage"] = True
            write_and_render(d, {"offer": offer_html(p)})
            n += 1
        print(f"re-rendered offer.pdf in {n} case dirs")
        return
    os.makedirs(OUT_ROOT, exist_ok=True)
    for p in PROFILES:
        p["_mrz"] = build_mrz(p)
        l1, l2 = p["_mrz"]
        assert len(l1) == 44 and len(l2) == 44
        d = os.path.join(OUT_ROOT, p["slug"])
        os.makedirs(d, exist_ok=True)
        print(f"\n== {p['slug']} ==  ({p['nationality']}) MRZ ok  {p['scenario']}")

        # NEVER clobber a sourced real passport image — those are hand-curated,
        # high-quality specimen scans the demo depends on. Only render a synthetic
        # SPECIMEN for profiles without a sourced image.
        if p.get("real_passport") and os.path.exists(os.path.join(d, "passport.png")):
            print("  passport.png (preserved sourced image)")
        else:
            render_passport(p, os.path.join(d, "passport.png"))
            print("  passport.png")

        docs = {"offer": offer_html(p), "lca": lca_html(p), "i94": i94_html(p),
                "degree": degree_html(p), "support-letter": support_html(p)}
        for n in p.get("extras", []):  # the 'too-much' over-shared client docs
            docs[n] = EXTRA_RENDERERS[n](p)
        write_and_render(d, docs)
        print("  " + ", ".join(f"{n}.pdf" for n in docs) + "  (html → _src/)")

        with open(os.path.join(d, "ground-truth.json"), "w") as f:
            json.dump(ground_truth(p), f, indent=2, ensure_ascii=False)
        print("  ground-truth.json")
    print(f"\nwrote {len(PROFILES)} case files under {OUT_ROOT}")

    build_adversarial()
    build_incomplete()


if __name__ == "__main__":
    sys.exit(main())
