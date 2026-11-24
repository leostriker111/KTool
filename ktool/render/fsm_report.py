"""Documento HTML para una maquina de estados.

Reutiliza el motor de minimizacion y los renders combinacionales: cada entrada
de flip-flop y cada salida es una tabla de verdad que pasa por `solve_output`.
"""

from __future__ import annotations

from ..core.simplify import solve_output
from ..fsm import flipflops
from . import kmap, circuit, codegen, fsm_diagram
from ._util import _esc
from .report import (_CSS, _CLIP_SCRIPT, _kmap_for_form, _seccion_portada, boton_copiar,
                     save_report)

_FF_NAME = {"D": "Tipo D", "T": "Tipo T", "JK": "JK", "SR": "SR"}

_EXTRA_CSS = """
@media print{h2,h3{break-after:avoid;} svg,.cwrap,.diagram,.card{break-inside:avoid;} .bt thead{display:table-header-group;} .bt tr{break-inside:avoid;}}
.diagram{background:#fff;border:1px solid #ddd;border-radius:6px;padding:10px;
  margin:10px 0;overflow-x:auto;text-align:center;}
.bt td,.bt th{border:1px solid #999;padding:2px 7px;text-align:center;font-size:12px;}
.bt th{background:#e8e8e8;} .bt .idx{color:#aaa;}
.bt .sep{border-left:2px solid #555;}
.bt .qn{background:#eef7ff;} .bt .exc{background:#fff4e8;} .bt .dc{color:#b8860b;}
.word{display:flex;flex-wrap:wrap;gap:6px;align-items:flex-end;margin:10px 0;
  background:#101010;padding:12px;border-radius:8px;}
.wordcell{text-align:center;}
.wordcell .c{color:#cfcf66;font-size:11px;font-family:Consolas,monospace;}
.steps{counter-reset:step;padding-left:0;list-style:none;}
.steps>li{margin:6px 0;padding-left:30px;position:relative;}
.steps>li:before{counter-increment:step;content:counter(step);position:absolute;
  left:0;top:0;background:#33518f;color:#fff;width:20px;height:20px;border-radius:50%;
  text-align:center;font-size:12px;line-height:20px;}
"""


def _summary(machine, ff_kind):
    rows = [
        ("Tipo", "Moore" if machine.kind == "moore" else "Mealy"),
        ("Estados", str(len(machine.states))),
        ("Entradas", ", ".join(machine.inputs) or "(ninguna)"),
        ("Bits de estado", ", ".join(machine.state_bits)),
        ("Flip-flop", _FF_NAME.get(ff_kind, ff_kind)),
        ("Salidas", ", ".join(machine.outputs) or "(ninguna)"),
    ]
    cells = "".join(f"<tr><th style='text-align:right'>{_esc(k)}</th>"
                    f"<td style='text-align:left'>{_esc(v)}</td></tr>" for k, v in rows)
    return f"<table class='shared'>{cells}</table>"


def _encoding_table(machine):
    head = "".join(f"<th>{_esc(b)}</th>" for b in machine.state_bits)
    rows = []
    for s in machine.states:
        bits = "".join(f"<td>{c}</td>" for c in s.code)
        rows.append(f"<tr><td><b>{_esc(s.label)}</b></td><td class='idx'>{_esc(s.name)}</td>{bits}</tr>")
    return (f"<table class='shared'><thead><tr><th>Estado</th><th>id</th>{head}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def _state_table(machine):
    """Una columna por variable: estado actual (Q..), entradas, estado
    siguiente (Q+..) y cada salida; no cadenas de bits pegadas."""
    qs = list(machine.state_bits)
    ths = ["Estado actual"] + qs + list(machine.inputs) + ["Estado sig."] \
        + [q + "+" for q in qs] + list(machine.outputs)
    n_q, n_i = len(qs), len(machine.inputs)
    sep = {1, 1 + n_q, 1 + n_q + n_i, 2 + n_q + n_i, 2 + 2 * n_q + n_i}
    head = "".join(f"<th{' class=\'sep\'' if k in sep else ''}>{_esc(h)}</th>"
                   for k, h in enumerate(ths))

    def bits(cadena, n):
        c = cadena if cadena else ""
        return [c[k] if k < len(c) else "-" for k in range(n)]

    rows = []
    for r in machine.state_table():
        st, dst = r["state"], r["next"]
        celdas = [f"<b>{_esc(st.label)}</b>"] + bits(st.code, n_q) + bits(r["inp"], n_i) \
            + [f"<b>{_esc(dst.label) if dst else '-'}</b>"] + bits(dst.code if dst else "", n_q) \
            + bits(r["out"], len(machine.outputs))
        tds = "".join(f"<td{' class=\'sep\'' if k in sep else ''}>{c}</td>"
                      for k, c in enumerate(celdas))
        rows.append(f"<tr>{tds}</tr>")
    return f"<table class='bt'><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _binary_table(variables, groups):
    """groups: lista de (etiqueta, {nombre: valores}). Filas sobre 2^len(variables)."""
    nv = len(variables)
    head = "<th>#</th>" + "".join(f"<th>{_esc(v)}</th>" for v in variables)
    for label, cols in groups:
        first = True
        for nm in cols:
            cls = "sep" if first else ""
            head += f"<th class='{cls}'>{_esc(nm)}</th>"
            first = False
    rows = []
    for i in range(1 << nv):
        bits = [(i >> (nv - 1 - k)) & 1 for k in range(nv)]
        cells = [f"<td class='idx'>{i}</td>"] + [f"<td>{b}</td>" for b in bits]
        for label, cols in groups:
            grp_cls = "qn" if label == "Q+" else ("exc" if label == "exc" else "")
            first = True
            for nm, vals in cols.items():
                v = vals[i]
                sep = "sep " if first else ""
                dc = "dc" if v == "x" else ""
                cells.append(f"<td class='{sep}{grp_cls} {dc}'>{v}</td>")
                first = False
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table class='bt'><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _forms_for(form, best):
    if form == "both":
        return ["sop", "pos"]
    if form in ("sop", "pos"):
        return [form]
    return [best.form]  # auto


def _signal_card(name, values, variables, form="auto", with_circuit=True):
    sol = solve_output(values, variables)
    out = ["<div class='outcard'>", f"<h3>Senal <code>{_esc(name)}</code></h3>", "<div class='eqs'>"]
    out.append(f"<div><b>SOP:</b> <code>{_esc(name)} = {_esc(sol['sop'].equation)}</code> "
               f"<span class='cost'>({sol['sop'].cost()[0]} comp, {sol['sop'].cost()[1]} lit)</span></div>")
    out.append(f"<div><b>POS:</b> <code>{_esc(name)} = {_esc(sol['pos'].equation)}</code> "
               f"<span class='cost'>({sol['pos'].cost()[0]} comp, {sol['pos'].cost()[1]} lit)</span></div>")
    if sol["xor"]:
        out.append(f"<div class='xor'>&#8853; <b>XOR/XNOR:</b> <code>{_esc(name)} = {_esc(sol['xor'].equation)}</code></div>")
    out.append(f"<div class='best'>&#9733; Mejor: <b>{sol['best'].form.upper()}</b> &rarr; "
               f"<code>{_esc(name)} = {_esc(sol['best'].equation)}</code></div>")
    out.append("</div>")

    forms = _forms_for(form, sol["best"])
    out.append("<div class='maps'>")
    for f in forms:
        label, pats, _ = _kmap_for_form(values, variables, sol, f)
        out.append("<div class='mapwrap'>")
        out.append(f"<div class='maplabel'>{label}</div>")
        out.append(kmap.kmap_svg(values, variables, pats))
        if pats:
            out.append("<div class='legend'>" + kmap.group_legend(pats, variables, "sop") + "</div>")
        out.append("</div>")
    out.append("</div>")
    if with_circuit:
        out.append("<div class='circuits'>")
        for f in forms:
            out.append("<div class='cwrap'>")
            out.append(f"<div class='maplabel'>Circuito {f.upper()}</div>")
            out.append(circuit.circuit_svg(sol[f], name))
            out.append("</div>")
        out.append("</div>")
    out.append("</div>")
    return "".join(out), sol


def _gates_table(gates):
    if not gates:
        return ""
    out = ["<table class='shared'><thead><tr><th>Compuerta</th><th>Termino</th>"
           "<th>Usada en</th></tr></thead><tbody>"]
    for g in gates:
        mark = " (compartida)" if len(g["outputs"]) > 1 else ""
        out.append(f"<tr><td><code>{_esc(g['id'])}</code></td><td><code>{_esc(g['term'])}</code></td>"
                   f"<td>{', '.join(map(_esc, g['outputs']))}{mark}</td></tr>")
    out.append("</tbody></table>")
    return "".join(out)


def _full_circuit(machine, ff_kind, exc_sols, out_sols, io_vars, out_vars):
    parts = ["<h2>7. Circuito completo (con flip-flops)</h2>",
             "<p class='hint'>La logica de excitacion alimenta las entradas de los flip-flops; sus "
             "salidas Q se realimentan a esa logica y van al decodificador. El circuito combinado va en "
             "SOP con las compuertas AND compartidas (para POS/XOR de una senal mira su circuito "
             "individual de arriba). Los rieles respetan el orden de entrada.</p>"]
    exc_sops = [(nm, s["sop"]) for nm, s in exc_sols if s["sop"].const is None]
    if exc_sops:
        svg, gates = circuit.build_shared_circuit(exc_sops, "sop", var_order=io_vars)
        parts.append("<h3>Logica de excitacion</h3>")
        parts.append(_gates_table(gates))
        parts.append("<div class='cwrap' style='overflow-x:auto;'>" + svg + "</div>")
    parts.append("<h3>Banco de flip-flops</h3>")
    parts.append("<p class='hint'>Cada salida de la excitacion entra al flip-flop del mismo nombre "
                 "(la senal D2/T2/J2 va al flip-flop de Q2). Reloj comun.</p>")
    parts.append("<div class='cwrap'>"
                 + circuit.flipflop_bank_svg(machine.state_bits, flipflops.inputs(ff_kind)) + "</div>")
    dec_sops = [(nm, s["sop"]) for nm, s in out_sols if s["sop"].const is None]
    if dec_sops:
        svg2, gates2 = circuit.build_shared_circuit(dec_sops, "sop", var_order=out_vars)
        parts.append("<h3>Decodificador de salida</h3>")
        parts.append(_gates_table(gates2))
        parts.append("<div class='cwrap' style='overflow-x:auto;'>" + svg2 + "</div>")
    return "".join(parts)


def _word_strip(machine):
    if machine.kind != "moore" or not machine.outputs:
        return ""
    # solo tiene sentido si las salidas son los segmentos a-g de un display
    if not set(o.lower() for o in machine.outputs) <= set("abcdefg") and \
            [o.lower() for o in machine.outputs] != list("abcdefg"):
        return ""
    cells = []
    for s in machine.states:
        if s.out is None:
            continue
        cells.append("<div class='wordcell'>"
                     + fsm_diagram.seg7_svg(s.out, machine.outputs, scale=0.5)
                     + f"<div class='c'>{_esc(s.label)} &middot; {_esc(s.code)}</div></div>")
    if not cells:
        return ""
    return ("<h3>Lo que muestra el display por estado</h3>"
            "<div class='word'>" + "".join(cells) + "</div>")


def _languages(machine, exc_sols, out_sols, langs):
    if langs is not None and len(langs) == 0:
        return ""
    chosen = langs or codegen.LANG_ORDER
    items = exc_sols + out_sols
    parts = ["<h2>Ecuaciones en varios lenguajes</h2>"]
    for lang in chosen:
        if lang not in codegen.OPS:
            continue
        lines = [codegen.render(s["best"], nm, lang) for nm, s in items]
        blob = "\n".join(lines)
        parts.append("<div class='langblock'>"
                     f"<div class='langhead'>{_esc(lang)} "
                     f"{boton_copiar(blob, lang)}</div>"
                     f"<pre class='langpre'>{_esc(blob)}</pre></div>")
    return "".join(parts)


def build_fsm_report(machine, ff_kind="JK", title=None, langs=None, circuit_on=True, form="auto",
                     portada=None, vhdl=True, fuente=None, kit_html=""):
    """El documento de una maquina. uente es el dict de la maquina (para el
    estado inicial y el banco de prueba del VHDL); portada, los datos de la
    portada formal (render/report.CAMPOS_PORTADA)."""
    ff_kind = flipflops.normalize(ff_kind)
    title = title or f"Maquina de estados: {machine.name}"
    io_vars = machine.io_variables()
    out_vars = machine.output_variables()

    nextcols = machine.nextstate_columns()
    exccols = machine.excitation_columns(ff_kind)
    outcols = machine.output_columns()

    body = [f"<h1>{_esc(title)}</h1>",
            "<p class='meta'>Diseno de maquina de estados sincrona con ktool</p>",
            _summary(machine, ff_kind)]

    body.append("<h2>1. Diagrama de estados</h2>")
    body.append("<div class='diagram'>" + fsm_diagram.state_diagram_svg(machine) + "</div>")
    body.append("<p class='hint'>Cada flecha lleva la condicion de entrada que dispara la transicion. "
                "Los lazos son transiciones que se quedan en el mismo estado.</p>")

    body.append("<h2>2. Asignacion de estados (codificacion)</h2>")
    body.append(_encoding_table(machine))

    body.append("<h2>3. Tabla de estados</h2>")
    body.append(_state_table(machine))

    body.append(f"<h2>4. Tabla de transiciones y excitacion ({_FF_NAME.get(ff_kind, ff_kind)})</h2>")
    body.append("<p class='hint'>Sobre las variables de estado y las entradas. <b>Q+</b> es el estado "
                "siguiente; las columnas de excitacion dicen que necesita cada flip-flop para lograr esa "
                "transicion. Las <span class='dc'>x</span> son don't care (cualquiera sirve) y son lo que "
                "acorta las ecuaciones.</p>")
    body.append(_binary_table(io_vars, [("Q+", nextcols), ("exc", exccols)]))

    body.append("<h2>5. Ecuaciones de excitacion de los flip-flops</h2>")
    body.append("<p class='hint'>Cada entrada de flip-flop se minimiza por separado con Quine-McCluskey "
                "(SOP, POS y XOR). La forma que se dibuja depende de --form (default: la mas barata).</p>")
    exc_sols = []
    for nm, vals in exccols.items():
        html, sol = _signal_card(nm, vals, io_vars, form=form, with_circuit=circuit_on)
        body.append(html)
        exc_sols.append((nm, sol))

    out_sols = []
    if machine.outputs:
        body.append("<h2>6. Decodificador de salida</h2>")
        body.append(_word_strip(machine))
        body.append("<p class='hint'>Cada segmento/salida es una funcion de "
                    f"{'las variables de estado' if machine.kind == 'moore' else 'estado y entradas'}.</p>")
        for nm, vals in outcols.items():
            html, sol = _signal_card(nm, vals, out_vars, form=form, with_circuit=circuit_on)
            body.append(html)
            out_sols.append((nm, sol))

    if circuit_on:
        body.append(_full_circuit(machine, ff_kind, exc_sols, out_sols, io_vars, out_vars))

    body.append(_languages(machine, exc_sols, out_sols, langs))

    if vhdl:
        body.append(_seccion_vhdl(fuente or _a_dict(machine), ff_kind))
    # el kit de hardware tal como se configuro en su ventana (gui/kit_ventana.py)
    body.append(kit_html)

    html = (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{_esc(title)}</title><style>{_CSS}{_EXTRA_CSS}</style></head>"
            f"<body>{''.join(body)}{_CLIP_SCRIPT}</body></html>")
    return html


def _a_dict(machine):
    """La maquina como dict (lo que espera hw/vhdl_fsm) cuando solo se tiene el objeto."""
    return {
        "name": machine.name, "kind": machine.kind, "inputs": machine.inputs,
        "state_bits": machine.state_bits, "outputs": machine.outputs,
        "states": [{"name": s.name, "code": s.code, "label": s.label, "out": s.out}
                   for s in machine.states],
        "transitions": [{"from": t.src, "in": t.inp, "to": t.dst, "out": t.out}
                        for t in machine.transitions],
    }


def _seccion_vhdl(fuente, ff_kind):
    """El VHDL por los tres metodos de la practica, y el banco de prueba que
    sirve para los tres. Si la maquina no se deja (nombres que chocan), lo dice."""
    from ..hw import vhdl_fsm
    try:
        bloques = [
            (f"Metodo 1: ecuaciones (flip-flops {ff_kind})", vhdl_fsm.por_ecuaciones(fuente, ff_kind)),
            ("Metodo 2: tabla de transicion", vhdl_fsm.por_tabla(fuente)),
            ("Metodo 3: diagrama de estados", vhdl_fsm.por_estados(fuente)),
            ("Banco de prueba (para cualquiera de los tres)",
             vhdl_fsm.banco_de_prueba(fuente, vhdl_fsm.estimulo_completo(fuente))),
        ]
    except (ValueError, KeyError) as e:
        return (f"<h2>8. VHDL</h2><p class='hint'>No se pudo generar el VHDL: "
                f"{_esc(str(e))}</p>")
    partes = ["<h2>8. VHDL por los tres metodos</h2>",
              "<p class='hint'>Los tres describen la misma maquina con la misma entidad: "
              "escoge el que pida la practica. El banco de prueba recorre todos los modos "
              "y cambios al azar, y compara cada ciclo con lo esperado. Reset asincrono "
              "en alto; para verlo en la MAX II, el reloj de 50 MHz se baja con un "
              "divisor.</p>"]
    for titulo, codigo in bloques:
        partes.append(
            f"<details class='guide'><summary>{_esc(titulo)}</summary>"
            f"<div class='langhead'>{boton_copiar(codigo)}</div>"
            f"<pre class='langpre'>{_esc(codigo)}</pre></details>")
    return "".join(partes)