#!/usr/bin/env python3
"""Composite a clean, valid ICAO TD3 MRZ (and minimal corrected fields) onto the
operator-provided realistic passport images, adopting each shown identity.

Per case: crop the source ABOVE its (broken/placeholder) MRZ band, render a fresh
valid MRZ strip from the persona, and append it — native-looking, no box-over-text.
India/Mexico also get small field overlays (name/number/dates) where the source is
placeholder/expired.

Output: passport-<case>.png in this dir (review copies). Same MRZ the generator's
build_mrz() would produce, so it matches ground-truth.json.
"""
import math, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MONO = subprocess.check_output(["fc-match","-f","%{file}","DejaVu Sans Mono"],text=True).strip()
SANSB = subprocess.check_output(["fc-match","-f","%{file}","DejaVu Sans:bold"],text=True).strip()

# ── ICAO 9303 TD3 MRZ (identical algorithm to generator/generate_cases.py) ──
def check_digit(s):
    w=[7,3,1]; t=0
    for i,c in enumerate(s):
        v = 0 if c=="<" else (int(c) if c.isdigit() else ord(c)-55)
        t += v*w[i%3]
    return str(t%10)

def mrz_name(surname, given):
    s=surname.upper().replace(" ","<"); g=given.upper().replace(" ","<")
    return (f"{s}<<{g}"+"<"*39)[:39]

def build_mrz(p):
    c=p["nationality"]
    l1=f"P<{c}{mrz_name(p['surname'],p['given'])}"; assert len(l1)==44,(len(l1),l1)
    pp=(p["passport_number"].upper()+"<"*9)[:9]; ppc=check_digit(pp)
    dob=p["dob"].replace("-","")[2:]; dc=check_digit(dob)
    exp=p["passport_expiration"].replace("-","")[2:]; ec=check_digit(exp)
    per="<"*14; pc=check_digit(per)
    comp=pp+ppc+dob+dc+exp+ec+per+pc; cc=check_digit(comp)
    l2=f"{pp}{ppc}{c}{dob}{dc}{p['sex']}{exp}{ec}{per}{pc}{cc}"; assert len(l2)==44,(len(l2),l2)
    return l1,l2

# ── personas (passport-visible identity; matches the operator images) ──
CASES = {
 "china": {
    "src":"china-source.png", "w":600, "crop_y":746, "strip_h":65, "mrz_pt":20,
    "surname":"ZHENGJIAN", "given":"YANGBEN", "nationality":"CHN",
    "sex":"F", "dob":"1985-03-20", "passport_number":"EF1260892",
    "passport_expiration":"2029-01-17",
    "overlays":[],  # name/number/dates already correct on the image
 },
 "india": {
    "src":"india-source.png", "w":570, "crop_y":350, "strip_h":46, "mrz_pt":18,
    "surname":"KUMAR", "given":"ARJUN", "nationality":"IND",
    "sex":"M", "dob":"1985-05-24", "passport_number":"P8401723",
    "passport_expiration":"2031-06-14",
    # source shows surname "SPECIMEN", given "KUMAR G", No "Z0000000" → cover + rewrite
    "overlays":[
      {"box":(232,40,330,66),  "text":"KUMAR",   "pt":15, "tx":236, "ty":58},
      {"box":(232,86,360,112), "text":"ARJUN",   "pt":15, "tx":236, "ty":104},
      {"box":(470,28,558,52),  "text":"P8401723","pt":13, "tx":474, "ty":46},
    ],
 },
 "mexico": {
    "src":"mexico-source.png", "w":618, "crop_y":396, "strip_h":40, "mrz_pt":20,
    "surname":"MEDINA PEREZ", "given":"ABIGAIL", "nationality":"MEX",
    "sex":"F", "dob":"1981-01-17", "passport_number":"J00000001",
    "passport_issue":"2022-06-12", "passport_expiration":"2032-06-11",
    # source expiry 12 06 2018 (expired) → bump issue/expiry to in-date
    "overlays":[
      {"box":(150,243,250,266), "text":"12 06 2022", "pt":12, "tx":152, "ty":260},
      {"box":(420,243,520,266), "text":"11 06 2032", "pt":12, "tx":422, "ty":260},
    ],
 },
}

def compose(key, c):
    src=os.path.join(HERE,c["src"]); out=os.path.join(HERE,f"passport-{key}.png")
    l1,l2=build_mrz(c)
    print(f"  {key}: {l1}")
    print(f"  {key}: {l2}")
    # 1. crop above the source MRZ band
    top=os.path.join(HERE,f".{key}-top.png")
    subprocess.run(["magick",src,"-crop",f"{c['w']}x{c['crop_y']}+0+0","+repage",top],check=True)
    # 2. fresh clean MRZ strip
    strip=os.path.join(HERE,f".{key}-strip.png")
    pt=c["mrz_pt"]; y1=int(c["strip_h"]*0.42); y2=int(c["strip_h"]*0.86)
    subprocess.run(["magick","-size",f"{c['w']}x{c['strip_h']}","xc:white",
        "-font",MONO,"-pointsize",str(pt),"-fill","#10222f",
        "-annotate",f"+22+{y1}",l1,"-annotate",f"+22+{y2}",l2,strip],check=True)
    # 3. append
    subprocess.run(["magick",top,strip,"-append",out],check=True)
    # 4. field overlays (cover source placeholder, write clean value)
    for ov in c.get("overlays",[]):
        x0,y0,x1,y1b=ov["box"]
        subprocess.run(["magick",out,"-fill","#f4f6f9","-stroke","none",
            "-draw",f"rectangle {x0},{y0} {x1},{y1b}",
            "-font",SANSB,"-pointsize",str(ov["pt"]),"-fill","#10222f",
            "-annotate",f"+{ov['tx']}+{ov['ty']}",ov["text"],out],check=True)
    print(f"  -> {out}")

if __name__=="__main__":
    keys=sys.argv[1:] or list(CASES)
    for k in keys:
        compose(k,CASES[k])
