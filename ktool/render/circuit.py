"""Render del circuito a SVG: rieles de literales + compuertas AND/OR."""

from __future__ import annotations

from ..core.simplify import term_literals
from ._util import _esc


from .. import theme


def _and_path(x, y, w, h):
    r = h / 2
    return (
        f'M {x},{y} L {x + w - r},{y} '
        f'A {r},{r} 0 0 1 {x + w - r},{y + h} '
        f'L {x},{y + h} Z'
    )


def _or_path(x, y, w, h):
    return (
        f'M {x},{y} Q {x + w*0.45},{y} {x + w},{y + h/2} '
        f'Q {x + w*0.45},{y + h} {x},{y + h} '
        f'Q {x + w*0.32},{y + h/2} {x},{y} Z'
    )


def _xor_gate(x, y, w, h):
    body = _or_path(x + 5, y, w - 5, h)
    return (
        f'<path d="{body}" fill="#222" stroke="#000"/>'
        f'<path d="M {x},{y} Q {x + w*0.30},{y + h/2} {x},{y + h}" '
        f'fill="none" stroke="#000" stroke-width="1.6"/>'
    )


def _gate_svg(kind, x, y, w, h):
    """Dibuja and/or/nand/nor. Las universales son la misma figura con bolita."""
    negada = kind in ("nand", "nor")
    base = "and" if kind in ("and", "nand") else "or"
    ancho = w - 8 if negada else w
    path = _and_path(x, y, ancho, h) if base == "and" else _or_path(x, y, ancho, h)
    svg = f'<path d="{path}" fill="#222" stroke="#000"/>'
    if negada:
        svg += (f'<circle cx="{x + ancho + 4}" cy="{y + h/2}" r="4" '
                f'fill="white" stroke="#000"/>')
    return svg


def _not_gate(x, y, h):
    return (
        f'<path d="M {x},{y} L {x},{y + h} L {x + h*0.85},{y + h/2} Z" '
        f'fill="#222" stroke="#000"/>'
        f'<circle cx="{x + h*0.85 + 4}" cy="{y + h/2}" r="4" fill="white" stroke="#000"/>'
    )


def solution_terms(solution):
    """Lista de terminos como listas de literales (str)."""
    invert = solution.form in ("pos", "nor")
    terms = []
    for p in solution.patterns:
        lits = term_literals(p, solution.variables, polarity_invert=invert)
        terms.append(lits or ["1"])
    return terms


def _xor_chain_svg(solution, output_name):
    vs = solution.xor_vars
    k = len(vs)
    gate_w, gate_h, gap = 44, 40, 66
    y = 48
    x0 = 70
    gates = max(1, k - 1)
    width = x0 + gates * (gate_w + gap) + (40 if solution.xnor else 0) + 60
    height = y + gate_h + 50

    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'font-family="Georgia, serif">'
    ]
    prev_out = None
    gx = x0
    for j in range(gates):
        top_y = y + gate_h * 0.3
        bot_y = y + gate_h * 0.72
        s.append(_xor_gate(gx, y, gate_w, gate_h))
        # entrada superior
        if prev_out is None:
            s.append(f'<line x1="{gx-30}" y1="{top_y}" x2="{gx}" y2="{top_y}" stroke="#000" stroke-width="1.5"/>')
            s.append(f'<text x="{gx-36}" y="{top_y+4}" font-size="13" text-anchor="end">{_esc(vs[0])}</text>')
        else:
            s.append(f'<line x1="{prev_out[0]}" y1="{prev_out[1]}" x2="{gx}" y2="{top_y}" stroke="#000" stroke-width="1.5"/>')
        # entrada inferior (variable nueva)
        new_var = vs[1] if prev_out is None else vs[j + 1]
        s.append(f'<line x1="{gx-30}" y1="{bot_y}" x2="{gx}" y2="{bot_y}" stroke="#000" stroke-width="1.5"/>')
        s.append(f'<text x="{gx-36}" y="{bot_y+4}" font-size="13" text-anchor="end">{_esc(new_var)}</text>')
        prev_out = (gx + gate_w, y + gate_h / 2)
        gx += gate_w + gap

    out_x, out_y = prev_out
    if solution.xnor:
        s.append(f'<line x1="{out_x}" y1="{out_y}" x2="{out_x+18}" y2="{out_y}" stroke="#000" stroke-width="1.5"/>')
        s.append(_not_gate(out_x + 18, out_y - 12, 24))
        out_x = out_x + 18 + 24 * 0.85 + 8
    s.append(f'<line x1="{out_x}" y1="{out_y}" x2="{out_x+34}" y2="{out_y}" stroke="#000" stroke-width="1.5"/>')
    s.append(f'<text x="{out_x+40}" y="{out_y+5}" font-size="15">{_esc(output_name)}</text>')
    s.append("</svg>")
    return "\n".join(s)


def circuit_svg(solution, output_name="Y"):
    form = solution.form
    if solution.const is not None:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="220" height="60" '
            f'font-family="Georgia">'
            f'<text x="10" y="35" font-size="16">{_esc(output_name)} = '
            f'constante {solution.const}</text></svg>'
        )

    if form == "xor":
        return _xor_chain_svg(solution, output_name)

    terms = solution_terms(solution)
    if not terms:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="50">'
            f'<text x="10" y="30" font-family="Georgia" font-size="15">{_esc(output_name)} = 0</text></svg>'
        )

    if form == "nand":
        inner_gate = outer_gate = "nand"
    elif form == "nor":
        inner_gate = outer_gate = "nor"
    elif form == "sop":
        inner_gate, outer_gate = "and", "or"
    else:
        inner_gate, outer_gate = "or", "and"
    universal = form in ("nand", "nor")

    # literales usados (rieles)
    literals = []
    for t in terms:
        for lit in t:
            if lit not in literals:
                literals.append(lit)
    literals.sort(key=lambda s: (s.rstrip("'"), s.endswith("'")))

    rail_gap = 28
    x0 = 16
    rail_x = {lit: x0 + i * rail_gap for i, lit in enumerate(literals)}
    rails_right = x0 + len(literals) * rail_gap + 24

    gate_w = 48
    top_pad = 40
    term_h = []
    term_y = []
    y = top_pad
    for t in terms:
        h = max(28, len(t) * 16)
        term_y.append(y)
        term_h.append(h)
        y += h + 26
    bottom = y + 20

    or_x = rails_right + gate_w + 60
    or_h = max(36, len(terms) * 18)
    or_y = (term_y[0] + term_y[-1] + term_h[-1]) / 2 - or_h / 2
    out_x = or_x + gate_w + 40

    width = out_x + 70
    height = max(bottom, or_y + or_h + 30)

    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'font-family="Georgia, serif">'
    ]

    # rieles verticales con etiqueta arriba
    for lit in literals:
        x = rail_x[lit]
        s.append(
            f'<line x1="{x}" y1="34" x2="{x}" y2="{bottom}" stroke="#bbb" stroke-width="1"/>'
        )
        s.append(
            f'<text x="{x}" y="26" font-size="13" text-anchor="middle">{_esc(lit)}</text>'
        )

    single_term = len(terms) == 1
    # NAND/NOR con un solo termino de un solo literal: las dos inversiones se
    # cancelan y no hace falta ninguna compuerta (Y = el literal, y ya)
    sin_compuertas = universal and single_term and len(terms[0]) == 1

    for j, t in enumerate(terms):
        gy = term_y[j]
        gh = term_h[j]
        gx = rails_right
        out_point_x = gx + gate_w
        out_point_y = gy + gh / 2

        if len(t) == 1 and (not universal or sin_compuertas):
            # un literal: conexion directa al riel, sin compuerta
            lit = t[0]
            x = rail_x[lit]
            s.append(
                f'<circle cx="{x}" cy="{out_point_y}" r="3" fill="#000"/>'
            )
            s.append(
                f'<line x1="{x}" y1="{out_point_y}" x2="{out_point_x}" y2="{out_point_y}" '
                f'stroke="#000" stroke-width="1.5"/>'
            )
        elif len(t) == 1:
            # en NAND/NOR el literal suelto SI necesita invertirse antes de la
            # compuerta final, o la funcion sale complementada
            lit = t[0]
            x = rail_x[lit]
            alto = min(gh, 26)
            s.append(_not_gate(gx, out_point_y - alto / 2, alto))
            s.append(f'<circle cx="{x}" cy="{out_point_y}" r="3" fill="#000"/>')
            s.append(
                f'<line x1="{x}" y1="{out_point_y}" x2="{gx}" y2="{out_point_y}" '
                f'stroke="#000" stroke-width="1.5"/>'
            )
            s.append(
                f'<line x1="{gx + alto * 0.85 + 8}" y1="{out_point_y}" '
                f'x2="{out_point_x}" y2="{out_point_y}" stroke="#000" stroke-width="1.5"/>'
            )
        else:
            s.append(_gate_svg(inner_gate, gx, gy, gate_w, gh))
            ninp = len(t)
            for k, lit in enumerate(t):
                iy = gy + gh * (k + 1) / (ninp + 1)
                x = rail_x[lit]
                s.append(f'<circle cx="{x}" cy="{iy}" r="3" fill="#000"/>')
                s.append(
                    f'<line x1="{x}" y1="{iy}" x2="{gx}" y2="{iy}" '
                    f'stroke="#000" stroke-width="1.5"/>'
                )

        if single_term:
            if universal and not sin_compuertas:
                # la compuerta final deshace la inversion de la primera; sin
                # ella la salida seria el complemento de la funcion
                alto = 24
                nx = out_point_x + 26
                s.append(
                    f'<line x1="{out_point_x}" y1="{out_point_y}" x2="{nx}" y2="{out_point_y}" '
                    f'stroke="#000" stroke-width="1.5"/>'
                )
                s.append(_not_gate(nx, out_point_y - alto / 2, alto))
                s.append(
                    f'<line x1="{nx + alto * 0.85 + 8}" y1="{out_point_y}" '
                    f'x2="{out_x}" y2="{out_point_y}" stroke="#000" stroke-width="1.5"/>'
                )
            else:
                s.append(
                    f'<line x1="{out_point_x}" y1="{out_point_y}" x2="{out_x}" y2="{out_point_y}" '
                    f'stroke="#000" stroke-width="1.5"/>'
                )
            s.append(
                f'<text x="{out_x + 6}" y="{out_point_y + 5}" font-size="15">{_esc(output_name)}</text>'
            )

    if not single_term:
        # compuerta final
        s.append(_gate_svg(outer_gate, or_x, or_y, gate_w, or_h))
        for j in range(len(terms)):
            iy = or_y + or_h * (j + 1) / (len(terms) + 1)
            oy = term_y[j] + term_h[j] / 2
            ox = rails_right + gate_w
            # salida de la compuerta interna hacia la final
            s.append(
                f'<line x1="{ox}" y1="{oy}" x2="{or_x - 8}" y2="{oy}" '
                f'stroke="#000" stroke-width="1.5"/>'
            )
            s.append(
                f'<line x1="{or_x - 8}" y1="{oy}" x2="{or_x - 8}" y2="{iy}" '
                f'stroke="#000" stroke-width="1.5"/>'
            )
            s.append(
                f'<line x1="{or_x - 8}" y1="{iy}" x2="{or_x}" y2="{iy}" '
                f'stroke="#000" stroke-width="1.5"/>'
            )
        oy = or_y + or_h / 2
        s.append(
            f'<line x1="{or_x + gate_w}" y1="{oy}" x2="{out_x}" y2="{oy}" '
            f'stroke="#000" stroke-width="1.5"/>'
        )
        s.append(
            f'<text x="{out_x + 6}" y="{oy + 5}" font-size="15">{_esc(output_name)}</text>'
        )

    s.append("</svg>")
    return "\n".join(s)


def build_shared_circuit(named_sops):
    """Circuito combinado en SOP con compuertas AND compartidas entre salidas.

    named_sops: lista de (nombre, Solution sop).
    Devuelve (svg, gates) donde gates = [{'id','term','outputs'}].
    """
    rails = []
    gate_terms = []        # {'lits','outputs'}
    gate_index = {}
    out_plan = []          # (name, inputs, const)
    for name, sol in named_sops:
        if sol.const is not None:
            out_plan.append((name, [], sol.const))
            continue
        terms = solution_terms(sol)
        if not terms:
            out_plan.append((name, [], 0))
            continue
        inputs = []
        for lits in terms:
            for lit in lits:
                if lit not in rails:
                    rails.append(lit)
            if len(lits) == 1:
                inputs.append(("lit", lits[0]))
            else:
                key = tuple(lits)
                if key not in gate_index:
                    gate_index[key] = len(gate_terms)
                    gate_terms.append({"lits": list(lits), "outputs": []})
                gi = gate_index[key]
                if name not in gate_terms[gi]["outputs"]:
                    gate_terms[gi]["outputs"].append(name)
                inputs.append(("gate", gi))
        out_plan.append((name, inputs, None))

    rails.sort(key=lambda lit: (lit.rstrip("'"), lit.endswith("'")))

    rail_gap, x0, top, gate_w, or_gate_w = 26, 16, 46, 46, 46
    rail_x = {lit: x0 + i * rail_gap for i, lit in enumerate(rails)}
    rails_right = x0 + len(rails) * rail_gap + 30

    and_pos = []
    y = top
    for g in gate_terms:
        gh = max(26, len(g["lits"]) * 14)
        and_pos.append((rails_right, y, gh))
        y += gh + 18
    and_bottom = y
    and_out_x = rails_right + gate_w
    and_cy = [gy + gh / 2 for (gx, gy, gh) in and_pos]

    slots = []
    oy = top
    for name, inputs, const in out_plan:
        if const is not None:
            slots.append({"name": name, "kind": "const", "y": oy, "h": 24, "const": const})
            oy += 42
        elif len(inputs) == 1:
            slots.append({"name": name, "kind": "direct", "y": oy, "h": 24, "inputs": inputs})
            oy += 42
        else:
            h = max(28, len(inputs) * 15)
            slots.append({"name": name, "kind": "or", "y": oy, "h": h, "inputs": inputs})
            oy += h + 22
    base_bottom = max(and_bottom, oy)

    # un "net" por fuente (compuerta AND o literal); cada uno toma un canal vertical propio
    nets = {}
    for si, slot in enumerate(slots):
        if slot["kind"] == "const":
            continue
        if slot["kind"] == "direct":
            inp = slot["inputs"][0]
            nets.setdefault(inp, {"targets": []})["targets"].append((slot["y"] + 12, "direct"))
        else:
            ninp = len(slot["inputs"])
            for k, inp in enumerate(slot["inputs"]):
                ty = slot["y"] + slot["h"] * (k + 1) / (ninp + 1)
                nets.setdefault(inp, {"targets": []})["targets"].append((ty, "or"))

    def _net_key(item):
        key = item[0]
        return (0, key[1]) if key[0] == "gate" else (1, rails.index(key[1]))

    net_items = sorted(nets.items(), key=_net_key)

    # carriles inferiores para los nets de un solo literal (no cruzan las AND)
    lane = {key: i for i, (key, _) in enumerate(k for k in net_items if k[0][0] == "lit")}
    lane_base = base_bottom + 10
    bottom_channel = lane_base + max(0, len(lane)) * 8 + 8

    def src_y_of(key):
        return and_cy[key[1]] if key[0] == "gate" else lane_base + lane[key] * 8

    # asignar columnas virtuales: si una ya tiene un vertical que solapa en Y, usa la siguiente
    tracks = []
    track_of = []
    for key, net in net_items:
        ys = [t[0] for t in net["targets"]] + [src_y_of(key)]
        a, b = min(ys), max(ys)
        net["span"] = (a, b)
        placed = None
        for ti, occ in enumerate(tracks):
            if all(b < oa - 2 or a > ob + 2 for oa, ob in occ):
                occ.append((a, b))
                placed = ti
                break
        if placed is None:
            tracks.append([(a, b)])
            placed = len(tracks) - 1
        track_of.append(placed)

    chan_x0, chan_step = and_out_x + 22, 16
    x_or = chan_x0 + len(tracks) * chan_step + 22
    x_out = x_or + or_gate_w + 80
    height = bottom_channel + 16
    width = x_out + 110

    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'font-family="Georgia, serif">'
    ]
    for lit in rails:
        x = rail_x[lit]
        s.append(f'<line x1="{x}" y1="34" x2="{x}" y2="{bottom_channel}" stroke="#bbb" stroke-width="1"/>')
        s.append(f'<text x="{x}" y="26" font-size="13" text-anchor="middle">{_esc(lit)}</text>')

    for gi, (gx, gy, gh) in enumerate(and_pos):
        lits = gate_terms[gi]["lits"]
        s.append(f'<path d="{_and_path(gx, gy, gate_w, gh)}" fill="#222" stroke="#000"/>')
        s.append(f'<text x="{gx + 6}" y="{gy - 3}" font-size="10" fill="#555">G{gi + 1}</text>')
        n = len(lits)
        for k, lit in enumerate(lits):
            iy = gy + gh * (k + 1) / (n + 1)
            rx = rail_x[lit]
            s.append(f'<circle cx="{rx}" cy="{iy}" r="3" fill="#000"/>')
            s.append(f'<line x1="{rx}" y1="{iy}" x2="{gx}" y2="{iy}" stroke="#000" stroke-width="1.4"/>')

    def dot(x, yy, color="#000", r=3):
        s.append(f'<circle cx="{x:.0f}" cy="{yy:.1f}" r="{r}" fill="{color}"/>')

    def wire(x1, y1, x2, y2, color):
        s.append(f'<line x1="{x1:.0f}" y1="{y1:.1f}" x2="{x2:.0f}" y2="{y2:.1f}" stroke="{color}" stroke-width="1.6"/>')

    for ni, (key, net) in enumerate(net_items):
        color = theme.WIRE_COLORS[ni % len(theme.WIRE_COLORS)]
        cx = chan_x0 + track_of[ni] * chan_step
        ymin, ymax = net["span"]
        sy = src_y_of(key)
        if key[0] == "gate":
            wire(and_out_x, sy, cx, sy, color)
            dot(and_out_x, sy)
        else:
            rx = rail_x[key[1]]
            dot(rx, sy)
            wire(rx, sy, cx, sy, color)
        s.append(f'<line x1="{cx}" y1="{ymin:.1f}" x2="{cx}" y2="{ymax:.1f}" stroke="{color}" stroke-width="1.6"/>')
        chan_ys = [sy]
        for ty, kind in net["targets"]:
            tx = x_or if kind == "or" else x_out
            wire(cx, ty, tx, ty, color)
            chan_ys.append(ty)
        for cyp in chan_ys:
            if ymin < cyp < ymax:
                dot(cx, cyp)

    for slot in slots:
        name, yy, h = slot["name"], slot["y"], slot["h"]
        if slot["kind"] == "const":
            s.append(f'<text x="{x_out - 30}" y="{yy + 16}" font-size="14">{_esc(name)} = {slot["const"]}</text>')
        elif slot["kind"] == "or":
            cy = yy + h / 2
            s.append(f'<path d="{_or_path(x_or, yy, or_gate_w, h)}" fill="#222" stroke="#000"/>')
            s.append(f'<line x1="{x_or + or_gate_w}" y1="{cy}" x2="{x_out}" y2="{cy}" stroke="#000" stroke-width="1.5"/>')
            s.append(f'<text x="{x_out + 6}" y="{cy + 5}" font-size="15">{_esc(name)}</text>')
        else:  # direct
            s.append(f'<text x="{x_out + 6}" y="{yy + 17}" font-size="15">{_esc(name)}</text>')

    s.append("</svg>")
    gates = [
        {"id": f"G{i + 1}", "term": "".join(g["lits"]), "outputs": list(g["outputs"])}
        for i, g in enumerate(gate_terms)
    ]
    return "\n".join(s), gates
