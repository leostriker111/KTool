"""Diagrama de estados y display de 7 segmentos en SVG (sin librerias)."""

from __future__ import annotations

import math

from ._util import _esc
from .. import theme

_ARROW = (
    '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" '
    'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    '<path d="M0,0 L10,5 L0,10 z" fill="#444"/></marker></defs>'
)


def _unit(dx, dy):
    d = math.hypot(dx, dy) or 1.0
    return dx / d, dy / d


def _node_positions(n, cx, cy, R):
    pos = {}
    for i in range(n):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        pos[i] = (cx + R * math.cos(ang), cy + R * math.sin(ang))
    return pos


def _edge_path(p1, p2, nr, bow):
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    ux, uy = _unit(p2[0] - p1[0], p2[1] - p1[1])
    px, py = -uy, ux  # perpendicular (mano izquierda)
    cxp, cyp = mx + px * bow, my + py * bow
    sx, sy = _unit(cxp - p1[0], cyp - p1[1])
    ex, ey = _unit(cxp - p2[0], cyp - p2[1])
    start = (p1[0] + nr * sx, p1[1] + nr * sy)
    end = (p2[0] + nr * ex, p2[1] + nr * ey)
    d = f"M {start[0]:.1f},{start[1]:.1f} Q {cxp:.1f},{cyp:.1f} {end[0]:.1f},{end[1]:.1f}"
    return d, (cxp, cyp)


def _self_loop(p, center, nr):
    ox, oy = _unit(p[0] - center[0], p[1] - center[1])  # hacia afuera
    tx, ty = -oy, ox
    a = (p[0] + nr * (ox * 0.5 + tx * 0.6), p[1] + nr * (oy * 0.5 + ty * 0.6))
    b = (p[0] + nr * (ox * 0.5 - tx * 0.6), p[1] + nr * (oy * 0.5 - ty * 0.6))
    c1 = (p[0] + nr * (ox * 2.4 + tx * 1.1), p[1] + nr * (oy * 2.4 + ty * 1.1))
    c2 = (p[0] + nr * (ox * 2.4 - tx * 1.1), p[1] + nr * (oy * 2.4 - ty * 1.1))
    d = (f"M {a[0]:.1f},{a[1]:.1f} C {c1[0]:.1f},{c1[1]:.1f} "
         f"{c2[0]:.1f},{c2[1]:.1f} {b[0]:.1f},{b[1]:.1f}")
    lbl = (p[0] + nr * ox * 2.7, p[1] + nr * oy * 2.7)
    return d, lbl


def _label(x, y, text):
    w = max(16, len(text) * 7 + 6)
    return (
        f'<rect x="{x - w/2:.1f}" y="{y - 9:.1f}" width="{w}" height="16" rx="3" '
        f'fill="#fffde8" stroke="#e0d9a8"/>'
        f'<text x="{x:.1f}" y="{y + 3:.1f}" font-size="11" text-anchor="middle" '
        f'fill="#7a5">{_esc(text)}</text>'
    )


def state_diagram_svg(machine):
    states = machine.states
    n = len(states)
    idx = {s.name: i for i, s in enumerate(states)}
    nr = 34
    R = max(120, int(n * 30))
    cx = cy = R + nr + 46
    size = 2 * (R + nr + 46)
    pos = _node_positions(n, cx, cy, R)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'font-family="Georgia, serif">', _ARROW,
    ]

    # transiciones agrupadas por (origen, destino)
    grouped = {}
    for t in machine.transitions:
        cond = _cond_label(machine, t)
        grouped.setdefault((t.src, t.dst), []).append(cond)

    for (src, dst), conds in grouped.items():
        label = ", ".join(c for c in conds if c)
        p1, p2 = pos[idx[src]], pos[idx[dst]]
        if src == dst:
            d, lbl = _self_loop(p1, (cx, cy), nr)
        else:
            d, lbl = _edge_path(p1, p2, nr, bow=34)
        out.append(f'<path d="{d}" fill="none" stroke="#444" stroke-width="1.6" '
                   f'marker-end="url(#ah)"/>')
        if label:
            out.append(_label(lbl[0], lbl[1], label))

    # nodos
    for i, s in enumerate(states):
        x, y = pos[i]
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{nr}" fill="#eef4ff" '
                   f'stroke="#33518f" stroke-width="2"/>')
        out.append(f'<text x="{x:.1f}" y="{y - 3:.1f}" font-size="17" '
                   f'font-weight="bold" text-anchor="middle" fill="#1a2a52">'
                   f'{_esc(s.label)}</text>')
        out.append(f'<text x="{x:.1f}" y="{y + 14:.1f}" font-size="11" '
                   f'text-anchor="middle" fill="#5a6a8a" '
                   f'font-family="Consolas, monospace">{_esc(s.code)}</text>')

    out.append("</svg>")
    return "\n".join(out)


def _cond_label(machine, t):
    if not machine.inputs:
        return ""
    parts = []
    for var, bit in zip(machine.inputs, t.inp):
        parts.append(var if bit == "1" else var + "'")
    cond = "".join(parts)
    if machine.kind == "mealy" and t.out is not None:
        cond += f" / {t.out}"
    return cond


# -- display de 7 segmentos --

def _hbar(x1, x2, y, t):
    h = t / 2
    return [x1, y, x1 + h, y - h, x2 - h, y - h, x2, y, x2 - h, y + h, x1 + h, y + h]


def _vbar(x, y1, y2, t):
    h = t / 2
    return [x, y1, x + h, y1 + h, x + h, y2 - h, x, y2, x - h, y2 - h, x - h, y1 + h]


def _seg7_polys():
    t, xL, xR, yT, yM, yB = 13, 26, 86, 24, 84, 144
    return [
        ("a", _hbar(xL, xR, yT, t)),
        ("b", _vbar(xR, yT, yM, t)),
        ("c", _vbar(xR, yM, yB, t)),
        ("d", _hbar(xL, xR, yB, t)),
        ("e", _vbar(xL, yM, yB, t)),
        ("f", _vbar(xL, yT, yM, t)),
        ("g", _hbar(xL, xR, yM, t)),
    ]


def seg7_svg(bits, segs=("a", "b", "c", "d", "e", "f", "g"), caption=None, scale=0.55):
    """Display de 7 segmentos. bits: cadena alineada a `segs` ('1' = encendido)."""
    on = {seg: (bits[i] == "1") for i, seg in enumerate(segs) if i < len(bits)}
    w, h = 112, 168
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w*scale:.0f}" '
           f'height="{(h + (26 if caption else 0))*scale:.0f}" '
           f'viewBox="0 0 {w} {h + (26 if caption else 0)}">']
    out.append(f'<rect x="0" y="0" width="{w}" height="{h}" rx="10" fill="{theme.DISP_BG}"/>')
    for name, poly in _seg7_polys():
        pts = " ".join(f"{poly[i]:.0f},{poly[i+1]:.0f}" for i in range(0, len(poly), 2))
        fill = theme.SEG_ON if on.get(name) else theme.SEG_OFF
        out.append(f'<polygon points="{pts}" fill="{fill}" stroke="#000"/>')
    if caption:
        out.append(f'<text x="{w/2:.0f}" y="{h + 18}" font-size="20" '
                   f'text-anchor="middle" fill="{theme.NAME_FG}" '
                   f'font-family="Georgia, serif">{_esc(caption)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def seg7_strip_svg(items, segs=("a", "b", "c", "d", "e", "f", "g"), captions=True):
    """Varios displays de 7 segmentos en fila, en un solo SVG.
    items: lista de cadenas de bits, o de pares (bits, caption)."""
    dw, dh, gap, pad = 112, 168, 18, 16
    cap_h = 28 if captions else 0
    norm = [(it if isinstance(it, tuple) else (it, None)) for it in items]
    w = pad * 2 + len(norm) * dw + (len(norm) - 1) * gap
    h = pad * 2 + dh + cap_h
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w} {h}" font-family="Georgia, serif">',
           f'<rect x="0" y="0" width="{w}" height="{h}" rx="14" fill="{theme.DISP_BG}"/>']
    for col, (bits, cap) in enumerate(norm):
        ox = pad + col * (dw + gap)
        on = {seg: (bits[i] == "1") for i, seg in enumerate(segs) if i < len(bits)}
        for name, poly in _seg7_polys():
            pts = " ".join(f"{poly[i] + ox:.0f},{poly[i+1] + pad:.0f}"
                           for i in range(0, len(poly), 2))
            fill = theme.SEG_ON if on.get(name) else theme.SEG_OFF
            out.append(f'<polygon points="{pts}" fill="{fill}" stroke="#000"/>')
        if captions and cap:
            out.append(f'<text x="{ox + dw/2:.0f}" y="{pad + dh + 20}" font-size="18" '
                       f'text-anchor="middle" fill="{theme.NAME_FG}">{_esc(cap)}</text>')
    out.append("</svg>")
    return "\n".join(out)
