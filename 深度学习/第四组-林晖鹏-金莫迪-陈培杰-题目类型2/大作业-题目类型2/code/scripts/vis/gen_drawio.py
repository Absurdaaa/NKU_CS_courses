"""Generate editable draw.io (diagrams.net) architecture diagrams.

Produces docs/figures/c3net.drawio and docs/figures/ctd.drawio. Open them at
https://app.diagrams.net to view/edit and export crisp PNG/SVG/PDF.
"""

import html
import os

ENC = "fillColor=#dae8fc;strokeColor=#6c8ebf;"   # encoder (blue)
DEC = "fillColor=#d5e8d4;strokeColor=#82b366;"   # decoder (green)
MOD = "fillColor=#ffe6cc;strokeColor=#d79b00;"   # special module (orange)
CTX = "fillColor=#f8cecc;strokeColor=#b85450;"   # context (red)
AUX = "fillColor=#e1d5e7;strokeColor=#9673a6;"   # boundary / aux (purple)
OUT = "fillColor=#fff2cc;strokeColor=#d6b656;"   # output (yellow)


def node(cid, text, x, y, w, h, style, fontsize=13):
    s = (f"rounded=1;whiteSpace=wrap;html=1;{style}fontSize={fontsize};"
         f"verticalAlign=middle;align=center;shadow=1;")
    return (f'<mxCell id="{cid}" value="{html.escape(text)}" style="{s}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


def edge(cid, src, tgt, dashed=False, label=""):
    s = ("edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;"
         "strokeColor=#555555;strokeWidth=1.5;")
    if dashed:
        s += "dashed=1;strokeColor=#999999;"
    return (f'<mxCell id="{cid}" value="{html.escape(label)}" style="{s}" edge="1" '
            f'parent="1" source="{src}" target="{tgt}"><mxGeometry relative="1" as="geometry"/></mxCell>')


def wrap(name, cells):
    body = "\n".join(cells)
    return (f'<diagram name="{name}">'
            f'<mxGraphModel dx="800" dy="600" grid="0" gridSize="10" guides="1" '
            f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            f'pageWidth="1100" pageHeight="720" math="0" shadow="0">'
            f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{body}</root>'
            f'</mxGraphModel></diagram>')


def c3net():
    c = []
    title = ('<mxCell id="t" value="C3Net-R18:  ResNet-18 + FPN  +  PPM context  +  CSCM contrast prior" '
             'style="text;html=1;fontSize=17;fontStyle=1;align=center;" vertex="1" parent="1">'
             '<mxGeometry x="120" y="10" width="860" height="30" as="geometry"/></mxCell>')
    c.append(title)
    # Encoder column
    enc = [("e0", "Input  3x352x352"), ("e1", "c0  (64, s2)"), ("e2", "c1  (64, s4)"),
           ("e3", "c2  (128, s8)"), ("e4", "c3  (256, s16)"), ("e5", "c4  (512, s32)")]
    for i, (cid, txt) in enumerate(enc):
        c.append(node(cid, txt, 40, 70 + i * 100, 200, 56, ENC))
    for i in range(5):
        c.append(edge(f"ee{i}", enc[i][0], enc[i + 1][0]))
    # PPM
    c.append(node("ppm", "PPM\nglobal context", 330, 570, 150, 56, CTX, 12))
    c.append(edge("e2ppm", "e5", "ppm"))
    # Decoder column (bottom->top)
    dec = [("d0", "top  (256)", OUT if False else DEC), ("d1", "decode3  (256, s16)", DEC),
           ("d2", "decode2  (128, s8)", DEC), ("d3", "decode1  (64, s4)", DEC),
           ("d4", "decode0  (64, s2)", DEC), ("d5", "head  ->  pred", OUT)]
    for i, (cid, txt, col) in enumerate(dec):
        y = 570 - i * 100
        c.append(node(cid, txt, 620, y, 220, 56, col))
    c.append(edge("ppm2top", "ppm", "d0"))
    for i in range(5):
        c.append(edge(f"dd{i}", dec[i][0], dec[i + 1][0]))
    # Skips
    skips = [("e4", "d1"), ("e3", "d2"), ("e2", "d3"), ("e1", "d4")]
    for i, (s, t) in enumerate(skips):
        c.append(edge(f"sk{i}", s, t, dashed=True, label="skip"))
    # CSCM modules
    for i, d in enumerate(["d2", "d3", "d4"]):
        cid = f"cscm{i}"
        y = 570 - (2 + i) * 100
        c.append(node(cid, "CSCM", 880, y, 110, 56, MOD, 12))
        c.append(edge(f"dc{i}", d, cid))
    # CSCM formula note
    c.append(node("note", "CSCM:  d_r = f - AvgPool_r(f),  r in {3,7,11}   ->   A = sigma(conv(bank))   ->   f * (1 + A)",
                  40, 678, 700, 40, MOD, 11))
    return wrap("C3Net", c)


def ctd():
    c = []
    title = ('<mxCell id="t" value="CTD-lite-R18:  Complementary Trilateral Decoder (Semantic / Spatial / Boundary)" '
             'style="text;html=1;fontSize=17;fontStyle=1;align=center;" vertex="1" parent="1">'
             '<mxGeometry x="120" y="10" width="900" height="30" as="geometry"/></mxCell>')
    c.append(title)
    c.append(node("enc", "ResNet-18\nEncoder\nc0 .. c4", 40, 250, 160, 120, ENC, 13))
    c.append(node("sem", "Semantic path\n(SAP global context)\n'where'", 280, 90, 230, 90, CTX, 12))
    c.append(node("spa", "Spatial path\n(FPN decode)\n'body'", 280, 270, 230, 90, DEC, 12))
    c.append(node("bnd", "Boundary path\n(deep + shallow fusion)\n'edges'", 280, 450, 230, 90, AUX, 12))
    for t in ("sem", "spa", "bnd"):
        c.append(edge(f"e_{t}", "enc", t))
    c.append(node("cam", "CAM\nCross\nAggregation", 600, 180, 150, 90, MOD, 12))
    c.append(edge("sem_cam", "sem", "cam"))
    c.append(edge("spa_cam", "spa", "cam"))
    c.append(node("brm", "BRM\nBoundary\nRefinement", 820, 270, 150, 90, MOD, 12))
    c.append(edge("cam_brm", "cam", "brm"))
    c.append(edge("bnd_brm", "bnd", "brm"))
    c.append(node("out", "decode0\nhead\n->  pred", 1030, 270, 130, 90, OUT, 12))
    c.append(edge("brm_out", "brm", "out"))
    c.append(node("note", "Restructure (not added capacity): each path is simpler, labour split by function.  "
                  "Deep supervision on semantic/spatial; Sobel(GT) on boundary.   ~12.3M params.",
                  40, 600, 900, 40, "fillColor=none;strokeColor=none;", 11))
    return wrap("CTD-lite", c)


if __name__ == "__main__":
    os.makedirs("docs/figures", exist_ok=True)
    for name, fn in [("c3net", c3net), ("ctd", ctd)]:
        xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="app.diagrams.net">{fn()}</mxfile>'
        with open(f"docs/figures/{name}.drawio", "w") as f:
            f.write(xml)
        print("wrote", f"docs/figures/{name}.drawio")
