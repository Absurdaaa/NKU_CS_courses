"""Render architecture diagrams for C3Net and CTD-lite (saved as PNG)."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ENC = "#cfe2f3"   # encoder
DEC = "#d9ead3"   # decoder
MOD = "#fce5cd"   # special module
CTX = "#f4cccc"   # context
AUX = "#ead1dc"   # auxiliary / supervision
OUT = "#fff2cc"   # output


def box(ax, x, y, w, h, text, color, fs=9, ls="-"):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                       linewidth=1.2, edgecolor="#444", facecolor=color, linestyle=ls)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs)
    return (x, y, w, h)


def arrow(ax, p1, p2, ls="-", color="#333"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=11,
                                 linewidth=1.1, color=color, linestyle=ls,
                                 shrinkA=2, shrinkB=2))


def c3net(path):
    fig, ax = plt.subplots(figsize=(12.5, 6.2))
    ax.set_xlim(0, 13); ax.set_ylim(0, 7); ax.axis("off")
    ax.set_title("C3Net-R18:  ResNet-18 + FPN  +  PPM context  +  CSCM contrast prior",
                 fontsize=12, weight="bold")

    # Encoder (left, top->down deeper)
    enc = [("Input 3x352x352", 6.0), ("c0 (64,s2)", 5.0), ("c1 (64,s4)", 4.0),
           ("c2 (128,s8)", 3.0), ("c3 (256,s16)", 2.0), ("c4 (512,s32)", 1.0)]
    eb = {}
    for name, y in enc:
        eb[name] = box(ax, 0.3, y, 2.4, 0.7, name, ENC)
    for i in range(len(enc) - 1):
        a = eb[enc[i][0]]; b = eb[enc[i + 1][0]]
        arrow(ax, (a[0] + a[2] / 2, a[1]), (b[0] + b[2] / 2, b[1] + b[3]))

    # Context: PPM on c4
    box(ax, 3.4, 1.0, 1.8, 0.7, "PPM\nglobal ctx", CTX, fs=8)
    arrow(ax, (2.7, 1.35), (3.4, 1.35))

    # Decoder (right, bottom->up)
    dec = [("top (256)", 1.0), ("decode3 (256,s16)", 2.0), ("decode2 (128,s8)", 3.0),
           ("decode1 (64,s4)", 4.0), ("decode0 (64,s2)", 5.0), ("head -> pred", 6.0)]
    db = {}
    for name, y in dec:
        col = OUT if "pred" in name else DEC
        db[name] = box(ax, 8.6, y, 2.7, 0.7, name, col)
    arrow(ax, (5.2, 1.35), (8.6, 1.35))  # PPM -> top
    for i in range(len(dec) - 1):
        a = db[dec[i][0]]; b = db[dec[i + 1][0]]
        arrow(ax, (a[0] + a[2] / 2, a[1] + a[3]), (b[0] + b[2] / 2, b[1]))

    # Skip connections encoder -> decoder
    skips = [("c3 (256,s16)", "decode3 (256,s16)"), ("c2 (128,s8)", "decode2 (128,s8)"),
             ("c1 (64,s4)", "decode1 (64,s4)"), ("c0 (64,s2)", "decode0 (64,s2)")]
    for e, d in skips:
        a = eb[e]; b = db[d]
        arrow(ax, (a[0] + a[2], a[1] + a[3] / 2), (b[0], b[1] + b[3] / 2), color="#999")

    # CSCM modules on decoder levels (the special module)
    for d in ["decode2 (128,s8)", "decode1 (64,s4)", "decode0 (64,s2)"]:
        b = db[d]
        box(ax, b[0] + 2.8, b[1] + 0.05, 1.0, 0.6, "CSCM", MOD, fs=8)
        arrow(ax, (b[0] + b[2], b[1] + b[3] / 2), (b[0] + 2.8, b[1] + 0.35))

    # Aux supervision (training only)
    box(ax, 8.6, 6.0 - 0.0, 0.0, 0.0, "", OUT)  # noop
    ax.text(9.95, 6.78, "edge head + side outputs (deep sup, training only)",
            fontsize=7.5, style="italic", color="#666")
    # CSCM detail box
    box(ax, 0.3, 0.05, 5.0, 0.62,
        "CSCM:  d_r = f - AvgPool_r(f),  r in {3,7,11}  ->  A=sigma(conv)  ->  f*(1+A)",
        MOD, fs=8)

    plt.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("saved", path)


def ctd(path):
    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    ax.set_xlim(0, 13); ax.set_ylim(0, 6); ax.axis("off")
    ax.set_title("CTD-lite-R18:  Complementary Trilateral Decoder (Semantic / Spatial / Boundary)",
                 fontsize=12, weight="bold")

    # Encoder
    enc = box(ax, 0.3, 2.2, 2.0, 1.4, "ResNet-18\nEncoder\nc0..c4", ENC, fs=9)

    # Three paths
    sem = box(ax, 3.2, 4.2, 2.6, 1.0, "Semantic path\n(SAP global ctx)\n'where'", CTX, fs=8)
    spa = box(ax, 3.2, 2.5, 2.6, 1.0, "Spatial path\n(FPN decode)\n'body'", DEC, fs=8)
    bnd = box(ax, 3.2, 0.8, 2.6, 1.0, "Boundary path\n(deep+shallow)\n'edges'", AUX, fs=8)
    for b in (sem, spa, bnd):
        arrow(ax, (enc[0] + enc[2], 2.9), (b[0], b[1] + b[3] / 2))

    # CAM: semantic + spatial
    cam = box(ax, 6.6, 3.35, 1.7, 1.0, "CAM\ncross\naggregation", MOD, fs=8)
    arrow(ax, (sem[0] + sem[2], sem[1] + 0.5), (cam[0], cam[1] + 0.7))
    arrow(ax, (spa[0] + spa[2], spa[1] + 0.5), (cam[0], cam[1] + 0.3))

    # BRM: + boundary
    brm = box(ax, 9.0, 2.7, 1.7, 1.0, "BRM\nboundary\nrefine", MOD, fs=8)
    arrow(ax, (cam[0] + cam[2], cam[1] + 0.5), (brm[0], brm[1] + 0.7))
    arrow(ax, (bnd[0] + bnd[2], bnd[1] + 0.5), (brm[0], brm[1] + 0.3))

    # head -> pred
    out = box(ax, 11.1, 2.7, 1.6, 1.0, "decode0\nhead\n-> pred", OUT, fs=8)
    arrow(ax, (brm[0] + brm[2], brm[1] + 0.5), (out[0], out[1] + 0.5))

    ax.text(0.3, 0.15,
            "Restructure (not added capacity): each path is simpler, labour split by function. "
            "Deep supervision on semantic/spatial; Sobel(GT) on boundary.  ~12.3M params.",
            fontsize=8, style="italic", color="#666")
    plt.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("saved", path)


if __name__ == "__main__":
    import os
    os.makedirs("docs/figures", exist_ok=True)
    c3net("docs/figures/c3net_arch.png")
    ctd("docs/figures/ctd_arch.png")
