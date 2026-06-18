#!/usr/bin/env python3
"""High-fidelity India + Mexico passport data-page replicas for the Pearson corpus.

Renders an authentic-looking passport (guilloche security background, national
emblem, real cropped face + ghost portrait, correct bilingual labels, valid ICAO
TD3 MRZ) for the adopted persona. Output: passport-<case>.png (review copies).

All data is synthetic; faces are the operator's specimen crops. ImageMagick only
(no PIL on this host).
"""
import math, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
def fc(q, fb="DejaVu-Sans"):
    try: return subprocess.check_output(["fc-match","-f","%{file}",q],text=True,stderr=subprocess.DEVNULL).strip() or fb
    except Exception: return fb
SANS, SANSB = fc("Liberation Sans"), fc("Liberation Sans:bold")
SERIF = fc("Noto Serif")
MONO = fc("Liberation Mono")
DEVA, DEVAB = fc("Noto Sans Devanagari"), fc("Noto Sans Devanagari:bold")
MONTHS=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]

# ── MRZ (ICAO 9303 TD3, same algo as the generator) ──
def cd(s):
    w=[7,3,1];t=0
    for i,c in enumerate(s):
        v=0 if c=="<" else (int(c) if c.isdigit() else ord(c)-55); t+=v*w[i%3]
    return str(t%10)
def mrz(p):
    nm=(p["surname"].upper().replace(" ","<")+"<<"+p["given"].upper().replace(" ","<")+"<"*39)[:39]
    l1=f"P<{p['nationality']}{nm}"
    pp=(p["passport_number"].upper()+"<"*9)[:9]; ppc=cd(pp)
    dob=p["dob"].replace("-","")[2:]; dc=cd(dob)
    exp=p["passport_expiration"].replace("-","")[2:]; ec=cd(exp)
    per="<"*14; pc=cd(per); comp=pp+ppc+dob+dc+exp+ec+per+pc
    l2=f"{pp}{ppc}{p['nationality']}{dob}{dc}{p['sex']}{exp}{ec}{per}{pc}{cd(comp)}"
    assert len(l1)==44 and len(l2)==44,(l1,l2)
    return l1,l2
def hdate(iso):
    y,m,d=iso.split("-"); return f"{int(d):02d} {MONTHS[int(m)-1]} {y}"

# ── guilloche: overlapping spirograph rosettes as thin polylines ──
def rosette(cx,cy,R,r,d,scale,turns,n,col,sw):
    pts=[]
    steps=int(turns*n)
    for i in range(steps+1):
        t=2*math.pi*turns*i/steps
        k=(R-r)/r
        x=cx+scale*((R-r)*math.cos(t)+d*math.cos(k*t))
        y=cy+scale*((R-r)*math.sin(t)-d*math.sin(k*t))
        pts.append(f"{x:.1f},{y:.1f}")
    return ["-stroke",col,"-strokewidth",str(sw),"-fill","none","-draw","polyline "+" ".join(pts)]

def wave_field(w,h,y0,y1,col,sw,rows=14,amp=9,per=26.0,phase=0.7):
    a=["-stroke",col,"-strokewidth",str(sw),"-fill","none"]
    for ri in range(rows):
        yy=y0+(y1-y0)*ri/(rows-1)
        pts=[f"{x},{yy+amp*math.sin(x/per+ri*phase):.1f}" for x in range(0,w+1,5)]
        a+=["-draw","polyline "+" ".join(pts)]
    return a

def wave_v(w,h,x0,x1,col,sw,cols=20,amp=8,per=24.0,phase=0.6):
    a=["-stroke",col,"-strokewidth",str(sw),"-fill","none"]
    for ci in range(cols):
        xx=x0+(x1-x0)*ci/(cols-1)
        pts=[f"{xx+amp*math.sin(y/per+ci*phase):.1f},{y}" for y in range(110,h-90,5)]
        a+=["-draw","polyline "+" ".join(pts)]
    return a

def guilloche(W,Hh,c1="#dde5f4",c2="#e6e3f0",r1="#d4ddef",r2="#ecdcc8"):
    # fine, dense, LIGHT interwoven field + two faint rosettes = secure-paper texture
    a =wave_field(W,Hh,120,Hh-95,c1,0.4,34,amp=7,per=30.0,phase=0.55)
    a+=wave_v(W,Hh,30,W-30,c2,0.4,26,amp=6,per=26.0,phase=0.5)
    a+=rosette(250,330,120,46,62,1.5,10,460,r1,0.32)
    a+=rosette(820,330,120,46,62,1.5,10,460,r2,0.32)
    return a

def seal(cx,cy,r,col):
    # stylized national medallion (concentric rings + radial ticks + star)
    a=["-stroke",col,"-strokewidth","2.2","-fill","none","-draw",f"circle {cx},{cy} {cx},{cy-r}"]
    a+=["-strokewidth","1.2","-draw",f"circle {cx},{cy} {cx},{cy-(r-7)}"]
    for k in range(36):
        ang=math.radians(k*10)
        a+=["-draw",f"line {cx+(r-7)*math.cos(ang):.1f},{cy+(r-7)*math.sin(ang):.1f} {cx+(r-3)*math.cos(ang):.1f},{cy+(r-3)*math.sin(ang):.1f}"]
    pts=[]
    for i in range(10):
        ang=math.radians(-90+i*36); rr=(r-12) if i%2==0 else (r-12)*0.45
        pts.append(f"{cx+rr*math.cos(ang):.1f},{cy+rr*math.sin(ang):.1f}")
    a+=["-fill",col,"-stroke","none","-draw","polygon "+" ".join(pts)]
    return a

def T(font,size,color,x,y,s,grav=None):
    o=["-font",font,"-pointsize",str(size),"-fill",color]
    if grav: o+=["-gravity",grav]
    o+=["-annotate",f"+{x}+{y}",s]
    if grav: o+=["-gravity","northwest"]
    return o

# ── India emblem: Ashoka-style chakra wheel ──
def chakra(cx,cy,r,col,sw=1.4):
    a=["-stroke",col,"-strokewidth",str(sw+0.8),"-fill","none","-draw",f"circle {cx},{cy} {cx},{cy-r}"]
    a+=["-strokewidth",str(sw)]
    for k in range(24):
        ang=math.radians(k*15)
        a+=["-draw",f"line {cx},{cy} {cx+(r-2)*math.cos(ang):.1f},{cy+(r-2)*math.sin(ang):.1f}"]
    a+=["-fill",col,"-stroke","none","-draw",f"circle {cx},{cy} {cx},{cy-3}"]
    return a

def render_india(p,face,out):
    W,Hh=1050,720
    INK="#16243f"; LBL="#5a6b86"; LINE="#9fb1d6"; SAFF="#e6b389"
    a=["-size",f"{W}x{Hh}","xc:#f4f2ec"]
    a+=guilloche(W,Hh)
    # top header
    a+=chakra(54,58,30,"#b8862e",1.4)
    a+=T(DEVAB,30,"#11317a",100,40,"भारत गणराज्य")
    a+=T(SANSB,21,"#11317a",100,78,"REPUBLIC OF INDIA")
    a+=["-fill","#1b2c52","-stroke","none","-draw","rectangle 40,104 1010,106"]
    # type / code / passport no (right)
    a+=T(SANS,13,LBL,300,128,"Type / प्रकार")
    a+=T(SANSB,20,INK,300,156,"P")
    a+=T(SANS,13,LBL,400,128,"Country Code / देश कोड")
    a+=T(SANSB,20,INK,400,156,p["nationality"])
    a+=T(SANS,13,LBL,620,128,"Passport No. / पासपोर्ट नं.")
    a+=T(SANSB,24,"#9a1b1b",620,158,p["passport_number"].upper())
    # photo (left) + frame
    a+=["-fill","#ffffff","-stroke","#9aa8c4","-strokewidth","1.5","-draw","rectangle 40,150 250,420","-stroke","none"]
    # ghost portrait (faint, right)
    # fields
    fx,vx=300,300
    rows=[("Surname / उपनाम",p["surname"].upper(),20),
          ("Given Name(s) / दिया गया नाम",p["given"].upper(),20),
          ("Nationality / राष्ट्रीयता",p["nationality_long"].upper(),18),
          ("Date of Birth / जन्म तिथि",hdate(p["dob"]),18),
          ("Place of Birth / जन्म स्थान",p["place_of_birth"].upper(),16),
          ("Place of Issue / जारी करने का स्थान",p["place_of_issue"].upper(),16),
          ("Date of Issue / जारी करने की तिथि",hdate(p["passport_issue"]),18),
          ("Date of Expiry / समाप्ति की तिथि",hdate(p["passport_expiration"]),18)]
    y=188
    for i,(lab,val,vs) in enumerate(rows):
        col = 0 if i<6 else 1
        if i==3: pass
        yy = [188,246,304,362,420,478,420,478][i] if False else None
    # simpler: left column rows 0..5, right column small block for sex + issue/expiry
    y=186
    layout=[("Surname / उपनाम",p["surname"].upper(),20,300,y),
            ("Given Name(s) / दिया गया नाम",p["given"].upper(),20,300,y+58),
            ("Nationality / राष्ट्रीयता",p["nationality_long"].upper(),18,300,y+116),
            ("Sex / लिंग",p["sex"],18,620,y+116),
            ("Date of Birth / जन्म तिथि",hdate(p["dob"]),18,300,y+174),
            ("Place of Birth / जन्म स्थान",p["place_of_birth"].upper(),15,620,y+174),
            ("Place of Issue / जारी करने का स्थान",p["place_of_issue"].upper(),15,300,y+232),
            ("Date of Issue / जारी करने की तिथि",hdate(p["passport_issue"]),17,620,y+232),
            ("Date of Expiry / समाप्ति की तिथि",hdate(p["passport_expiration"]),17,300,y+290)]
    for lab,val,vs,lx,ly in layout:
        a+=T(SANS,12,LBL,lx,ly,lab)
        a+=T(SANSB,vs,INK,lx,ly+24,val)
    # signature
    a+=T(SERIF,26,"#26324d",300,y+352,"A. Kumar")
    a+=T(SANS,11,LBL,300,y+366,"Signature of Bearer / धारक के हस्ताक्षर")
    # MRZ band
    l1,l2=mrz(p)
    a+=["-fill","#ffffff","-stroke","none","-draw",f"rectangle 0,636 {W},{Hh}"]
    a+=["-font",MONO,"-pointsize","27","-fill","#10222f","-annotate","+30+676",l1,"-annotate","+30+716",l2]
    a+=["-strokewidth","1","-stroke","#cfd6e6","-fill","none","-draw",f"line 0,636 {W},636","-stroke","none"]
    subprocess.run(["magick",*a,out+".base.png"],check=True)
    # composite the real face into the photo box + a faint ghost on the right
    subprocess.run(["magick",out+".base.png",
        "(",face,"-resize","206x266^","-gravity","center","-extent","206x266",")",
        "-gravity","NorthWest","-geometry","+42+152","-composite",
        "(",face,"-resize","156x198^","-gravity","center","-extent","156x198",
            "-alpha","set","-channel","A","-evaluate","multiply","0.14","+channel",")",
        "-gravity","NorthWest","-geometry","+800+150","-composite", out],check=True)
    for t in (".base.png",):
        try: os.remove(out+t)
        except OSError: pass
    print(f"  india -> {out}\n   {l1}\n   {l2}")

def mxd(iso):
    y,m,d=iso.split("-"); return f"{int(d):02d} {int(m):02d} {y}"

def render_mexico(p,face,out):
    W,Hh=1050,720
    GRN="#1f6e49"; INK="#173a2c"; LBL="#5c7268"
    a=["-size",f"{W}x{Hh}","xc:#eef4ee"]
    a+=guilloche(W,Hh,"#cfe2d5","#dcebe1","#cfe2d5","#e7ddc9")
    # header
    a+=seal(56,58,30,GRN)
    a+=T(SANS,13,LBL,100,32,"Pasaporte / Passport")
    a+=T(SANSB,25,GRN,100,68,"ESTADOS UNIDOS MEXICANOS")
    a+=["-fill",GRN,"-stroke","none","-draw","rectangle 40,104 1010,106"]
    a+=T(SANS,13,LBL,300,128,"Tipo / Type")
    a+=T(SANSB,20,INK,300,156,"P")
    a+=T(SANS,13,LBL,400,128,"Clave / Code")
    a+=T(SANSB,20,INK,400,156,p["nationality"])
    a+=T(SANS,13,LBL,620,128,"Pasaporte No. / Passport No.")
    a+=T(SANSB,24,"#9a1b1b",620,158,p["passport_number"].upper())
    a+=["-fill","#ffffff","-stroke","#a7c0b2","-strokewidth","1.5","-draw","rectangle 40,150 250,420","-stroke","none"]
    y=186
    layout=[("Apellidos / Surname",p["surname"].upper(),20,300,y),
            ("Nombre(s) / Given Names",p["given"].upper(),20,300,y+58),
            ("Nacionalidad / Nationality","MEXICANA",18,300,y+116),
            ("Sexo / Sex",p["sex"],18,620,y+116),
            ("CURP",p["curp"],16,620,y+58),
            ("Fecha de nacimiento / Date of birth",mxd(p["dob"]),18,300,y+174),
            ("Lugar de nacimiento / Place of birth",p["place_of_birth"].upper(),15,620,y+174),
            ("Fecha de expedición / Date of issue",mxd(p["passport_issue"]),17,300,y+232),
            ("Fecha de caducidad / Date of expiry",mxd(p["passport_expiration"]),17,620,y+232),
            ("Autoridad / Authority","SRE",15,300,y+290)]
    for lab,val,vs,lx,ly in layout:
        a+=T(SANS,12,LBL,lx,ly,lab); a+=T(SANSB,vs,INK,lx,ly+24,val)
    a+=T(SERIF,26,"#26443a",620,y+322,"A. Medina")
    a+=T(SANS,11,LBL,620,y+336,"Firma del Titular / Signature")
    l1,l2=mrz(p)
    a+=["-fill","#ffffff","-stroke","none","-draw",f"rectangle 0,636 {W},{Hh}"]
    a+=["-font",MONO,"-pointsize","27","-fill","#10222f","-annotate","+30+676",l1,"-annotate","+30+716",l2]
    a+=["-strokewidth","1","-stroke","#c7dccd","-fill","none","-draw",f"line 0,636 {W},636","-stroke","none"]
    subprocess.run(["magick",*a,out+".base.png"],check=True)
    subprocess.run(["magick",out+".base.png",
        "(",face,"-resize","206x266^","-gravity","center","-extent","206x266",")",
        "-gravity","NorthWest","-geometry","+42+152","-composite",
        "(",face,"-resize","156x198^","-gravity","center","-extent","156x198",
            "-alpha","set","-channel","A","-evaluate","multiply","0.13","+channel",")",
        "-gravity","NorthWest","-geometry","+800+150","-composite", out],check=True)
    try: os.remove(out+".base.png")
    except OSError: pass
    print(f"  mexico -> {out}\n   {l1}\n   {l2}")

INDIA={"surname":"KUMAR","given":"ARJUN","nationality":"IND","nationality_long":"Indian",
 "sex":"M","dob":"1985-05-24","place_of_birth":"Mumbai, Maharashtra","place_of_issue":"Mumbai",
 "passport_number":"P8401723","passport_issue":"2021-06-15","passport_expiration":"2031-06-14"}
MEXICO={"surname":"MEDINA PEREZ","given":"ABIGAIL","nationality":"MEX",
 "sex":"F","dob":"1981-01-17","place_of_birth":"Ciudad de Mexico","curp":"MEPA810117MDFGRZ09",
 "passport_number":"G14820073","passport_issue":"2022-06-12","passport_expiration":"2032-06-11"}

if __name__=="__main__":
    what=sys.argv[1:] or ["india","mexico"]
    if "india" in what:
        render_india(INDIA, os.path.join(HERE,"india-face.png"), os.path.join(HERE,"passport-india.png"))
    if "mexico" in what:
        render_mexico(MEXICO, os.path.join(HERE,"mexico-face.png"), os.path.join(HERE,"passport-mexico.png"))
