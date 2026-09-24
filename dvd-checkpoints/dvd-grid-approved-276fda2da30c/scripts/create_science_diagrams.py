import html
import json
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path.cwd()
OUT = ROOT / "visuals/science-diagrams"
OUT.mkdir(parents=True, exist_ok=True)
SCI = ROOT / "visuals/science-originals"
S = 3
BG = "#061019"
WHITE = "#edf6ff"
CYAN = "#75d8ff"
MUTED = "#acc3d3"
GOLD = "#ffd68a"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
records = []

def coords(values):
    return tuple(round(v*S) for v in values)

def text(x, y, value, size=26, color=WHITE, anchor="mm"):
    d.text(coords((x,y)), value,
           font=ImageFont.truetype(FONT, size*S),
           fill=color, anchor=anchor)

def line(points, color=CYAN, width=2):
    d.line([coords(p) for p in points], fill=color, width=width*S)

def ellipse(box, fill=None, outline=None, width=2):
    d.ellipse(coords(box), fill=fill, outline=outline, width=width*S)

def dot(x,y,r,color):
    ellipse((x-r,y-r,x+r,y+r),fill=color)

def begin(title, note="Illustration · Sizes and distances not to scale"):
    global im,d
    im = Image.new("RGB",(1280*S,720*S),BG)
    d = ImageDraw.Draw(im)
    text(640,60,title,38,CYAN)
    text(640,658,note,21,MUTED)

def photo(name,box):
    path = next((SCI/name).parent.glob((SCI/name).name))
    x0,y0,x1,y1 = box
    with Image.open(path) as source:
        image = ImageOps.contain(
            source.convert("RGB"),
            (round((x1-x0)*S),round((y1-y0)*S)),
            method=Image.Resampling.LANCZOS,
        )
        im.paste(image,(
            round(x0*S)+round(((x1-x0)*S-image.width)/2),
            round(y0*S)+round(((y1-y0)*S-image.height)/2),
        ))

def save(name,title,source,description):
    path=OUT/f"{name}.png"
    im.save(path)
    records.append({
        "name":name,"title":title,"file":str(path),
        "width":im.width,"height":im.height,
        "type":"educational illustration",
        "source":source,"description":description,
        "credit":"Best Polity LLC / Rift Signal",
    })
    print(f"CREATED: {name} — {im.width} x {im.height}",flush=True)

solar="https://science.nasa.gov/solar-system/"
helio="https://science.nasa.gov/heliophysics/focus-areas/heliosphere/"
galaxies="https://science.nasa.gov/universe/galaxies/large-scale-structures/"
mw="https://imagine.gsfc.nasa.gov/features/cosmic/milkyway_info.html"
universe="https://www.nasa.gov/science-research/astrophysics/how-big-is-space-we-asked-a-nasa-expert-episode-61/"

begin("Earth and the Moon","Photo diagram · Gap shortened; worlds enlarged")
photo("earth.jpg",(120,165,580,565))
photo("moon.tif",(850,260,1050,460))
line([(605,365),(815,365)],MUTED,2)
text(350,595,"Earth",30)
text(950,500,"Moon",30)
save("earth-moon","Earth and the Moon",solar,
     "NASA Earth composite and SVS Moon mosaic; comparison not to scale.")

begin("Our solar system")
dot(110,340,65,GOLD)
text(110,455,"Sun",27)
planets=[
    ("Mercury",265,13,"#a5a5a5"),
    ("Venus",390,22,"#dec494"),
    ("Earth",515,24,"#6cbbef"),
    ("Mars",640,18,"#d98764"),
    ("Jupiter",765,49,"#d1ad87"),
    ("Saturn",910,39,"#e2ce9b"),
    ("Uranus",1060,29,"#99d8dc"),
    ("Neptune",1180,29,"#678bea"),
]
for name,x,r,color in planets:
    if name=="Saturn":
        ellipse((x-65,326,x+65,354),outline="#b6a88d",width=7)
    dot(x,340,r,color)
    if name=="Saturn":
        d.arc(coords((x-65,326,x+65,354)),0,180,fill="#ded0ad",width=7*S)
    y=420 if name not in ("Venus","Mars","Saturn","Neptune") else 470
    line([(x,340+r+10),(x,y-24)],MUTED,1)
    text(x,y,name,23)
text(640,560,"Eight planets orbit the Sun.",29)
save("solar-system","Our solar system",solar,
     "Planets in order; symbols, sizes and spacing are illustrative.")

begin("The heliosphere","Schematic · Shape, sizes and distances simplified")
ellipse((250,175,1030,565),fill="#102b3e",outline=CYAN,width=4)
dot(555,370,33,GOLD)
text(555,435,"Sun",27)
for angle in (-145,-95,-45,5,55,105,155):
    a=math.radians(angle)
    p=(555+65*math.cos(a),370+65*math.sin(a))
    q=(555+140*math.cos(a),370+140*math.sin(a))
    line([p,q],GOLD,3)
    for delta in (-.45,.45):
        back=(q[0]-17*math.cos(a+delta),q[1]-17*math.sin(a+delta))
        line([q,back],GOLD,3)
text(805,370,"Solar wind",29)
text(640,125,"A region shaped by the Sun's wind",29)
text(1030,590,"Heliopause",25)
line([(985,560),(940,525)],MUTED,2)
text(145,355,"Interstellar",23)
text(145,390,"space",23)
save("heliosphere","The heliosphere",helio,
     "Solar wind region and heliopause; not a solar-system outer boundary map.")

begin("The Milky Way","Illustration · View from above; positions approximate")
cx,cy=495,355
rng=random.Random(2044)
for arm in range(4):
    points=[]
    for j in range(160):
        f=j/159
        radius=55+220*f
        angle=arm*math.pi/2+f*3.8
        x=cx+radius*math.cos(angle)
        y=cy+.72*radius*math.sin(angle)
        points.append((x,y))
        for _ in range(3):
            dot(x+rng.gauss(0,9),y+rng.gauss(0,7),
                rng.uniform(.8,2.1),rng.choice(["#82bcd9","#b6d6e5","#597c9a"]))
    line(points,"#45677f",3)
ellipse((cx-65,cy-27,cx+65,cy+27),fill="#d9c99d")
sx,sy=cx+178,cy+55
ellipse((sx-13,sy-13,sx+13,sy+13),outline=GOLD,width=3)
line([(sx+15,sy),(850,sy),(885,375)],GOLD,2)
text(1030,350,"Our solar system",26)
text(1030,395,"in the Orion region",23,MUTED)
text(500,590,"Our home galaxy",29)
save("milky-way","The Milky Way",mw,
     "Simplified barred spiral; solar-system marker is approximate, not a measured map.")

def galaxy_icon(x,y,r,tilt=0):
    ellipse((x-r,y-r*.36,x+r,y+r*.36),fill="#526d85")
    ellipse((x-r*.65,y-r*.22,x+r*.65,y+r*.22),fill="#9baab4")
    ellipse((x-r*.22,y-r*.16,x+r*.22,y+r*.16),fill="#eadbbe")

begin("The Local Group","Schematic · Selected members; positions and sizes not to scale")
galaxy_icon(345,325,105)
galaxy_icon(875,300,130)
galaxy_icon(810,495,60)
text(345,400,"Milky Way",29)
text(875,385,"Andromeda",29)
text(810,560,"Triangulum",27)
for x,y in [(180,230),(235,450),(450,205),(1015,230),(1070,440),(945,530)]:
    dot(x,y,8,"#92acc1")
text(340,555,"Many smaller galaxies",24,MUTED)
save("local-group","The Local Group",galaxies,
     "Conceptual membership diagram, not a map of actual directions or distances.")

begin("The cosmic web","Schematic · Galaxy distribution, not a photograph")
points=[(170,220),(415,180),(730,245),(1030,190),(1130,420),
        (935,545),(660,475),(380,550),(145,445),(420,350)]
edges=[(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7),(7,8),
       (8,0),(1,9),(9,8),(9,6),(2,6)]
rng=random.Random(59)
for a,b in edges:
    x0,y0=points[a];x1,y1=points[b]
    line([(x0,y0),(x1,y1)],"#29475d",4)
    for j in range(90):
        t=rng.random()
        x=x0+(x1-x0)*t+rng.gauss(0,7)
        y=y0+(y1-y0)*t+rng.gauss(0,7)
        dot(x,y,rng.uniform(1,2.5),"#7caecb")
for x,y in points:
    for _ in range(55):
        dot(x+rng.gauss(0,13),y+rng.gauss(0,13),
            rng.uniform(1,3),"#cfdfeb")
text(840,370,"Void",30)
text(600,155,"Filament",26)
line([(590,177),(565,205)],GOLD,2)
text(640,600,"Galaxies gather along strands and around knots.",25)
save("cosmic-web","The cosmic web",galaxies,
     "Invented schematic distribution; filaments and underdense voids, not a survey.")

begin("The observable universe","Concept diagram · This is not a physical edge")
ellipse((390,130,890,630),outline=CYAN,width=4)
rng=random.Random(7)
for _ in range(260):
    angle=rng.random()*2*math.pi
    radius=math.sqrt(rng.random())*230
    dot(640+radius*math.cos(angle),380+radius*math.sin(angle),
        rng.uniform(1,3),"#728ea6")
dot(640,380,11,GOLD)
text(640,420,"Us",25)
text(170,320,"The region we",24)
text(170,355,"can receive",24)
text(170,390,"signals from",24)
line([(290,375),(395,375)],MUTED,2)
text(1085,310,"The whole universe",23)
text(1085,350,"may extend",23)
text(1085,390,"much farther.",23)
save("observable-universe","The observable universe",universe,
     "Observer-centered horizon diagram; the observer is not the center of the whole universe.")

begin("An elliptical galaxy","Illustration · A simplified galaxy shape")
rng=random.Random(81)
for _ in range(8500):
    x=rng.gauss(640,160)
    y=rng.gauss(355,82)
    if 130<x<1150 and 140<y<570:
        distance=((x-640)/160)**2+((y-355)/82)**2
        color="#f4dfb8" if distance<1 else "#928b84"
        dot(x,y,rng.uniform(.5,1.8),color)
text(640,585,"A smooth, rounded or oval appearance",28)
save("elliptical-galaxy","An elliptical galaxy",
     "https://science.nasa.gov/universe/galaxies/",
     "Illustrative stellar distribution, not a photograph of a named galaxy.")

(OUT/"manifest.json").write_text(json.dumps(records,indent=2)+"\n")
gallery='''<!doctype html><html><meta charset="utf-8">
<title>Rift Signal science diagrams</title>
<style>body{background:#061019;color:#edf6ff;font:20px sans-serif;margin:24px}
img{display:block;width:100%;max-width:1200px;margin:12px 0 40px}
a{color:#75d8ff}</style><h1>Rift Signal — science diagrams</h1>
<p>Click any image to view it at full resolution.</p>'''
for row in records:
    name=Path(row["file"]).name
    gallery+=f'<h2>{html.escape(row["title"])}</h2><a href="{name}"><img src="{name}"></a>'
gallery+='</html>'
(OUT/"index.html").write_text(gallery)
print("\nSUCCESS: eight 3840 x 2160 science diagrams created.")
print("Illustration and scale notes included.")
print("Review gallery:",OUT/"index.html")
print("No DVD rebuilt or burned.")
