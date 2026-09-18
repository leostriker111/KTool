"""Arma el documento HTML con todos los resultados."""

from __future__ import annotations

import os
import tempfile
import webbrowser

from ..core.simplify import solve_output, shared_terms
from . import kmap, circuit, codegen
from ._util import _esc, _attr


class Options:
    def __init__(
        self,
        form="auto",        # 'sop' | 'pos' | 'nand' | 'nor' | 'auto' | 'both'
        kmap=True,
        circuit=True,
        table=True,
        shared=True,
        title="Resultados ktool",
        langs=None,         # None = todos; [] = ninguno; lista = solo esos
    ):
        self.form = form
        self.kmap = kmap
        self.circuit = circuit
        self.table = table
        self.shared = shared
        self.title = title
        self.langs = langs


def _forms_to_show(opt, best):
    if opt.form == "both":
        return ["sop", "pos"]
    if opt.form in ("sop", "pos", "nand", "nor"):
        return [opt.form]
    return [best.form]  # auto


def _truth_table_html(table):
    has_notes = any(n for n in table.notes)
    head = ["#"] + table.variables + list(table.outputs.keys())
    if has_notes:
        head.append("nota")
    ths = "".join(f"<th>{_esc(h)}</th>" for h in head)
    rows = []
    for i in range(table.rows):
        cells = [f"<td class='idx'>{i}</td>"]
        for b in table.bits(i):
            cells.append(f"<td>{b}</td>")
        for name in table.outputs:
            v = table.outputs[name][i]
            cls = "dc" if v == "x" else ("one" if v == 1 else "zero")
            cells.append(f"<td class='{cls}'>{v}</td>")
        if has_notes:
            cells.append(f"<td class='note'>{_esc(table.notes[i])}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table class='tt'><thead><tr>{ths}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _table_tsv(table):
    has_notes = any(n for n in table.notes)
    head = ["#"] + table.variables + list(table.outputs.keys())
    if has_notes:
        head.append("nota")
    lines = ["\t".join(head)]
    for i in range(table.rows):
        cells = [str(i)] + [str(b) for b in table.bits(i)]
        cells += [str(table.outputs[name][i]) for name in table.outputs]
        if has_notes:
            cells.append(table.notes[i])
        lines.append("\t".join(cells))
    return "\n".join(lines)


_GUIDE = """
<details class="guide" open><summary>Como leer este documento</summary>
<div class="guidebody">
<p>Cada <b>salida</b> se minimiza por separado con el metodo de Quine-McCluskey
(exacto, maneja don't cares). Se calculan tres caminos y se elige el mas barato
por numero de compuertas:</p>
<ul>
<li><b>SOP</b> (suma de productos): compuertas AND hacia una OR.</li>
<li><b>POS</b> (producto de sumas): compuertas OR hacia una AND.</li>
<li><b>XOR/XNOR</b>: cuando la funcion es la paridad de un grupo de variables,
suele ser la realizacion mas economica.</li>
</ul>
<p>En el <b>mapa de Karnaugh</b> cada grupo va en un color y su termino aparece en
la leyenda. Las celdas <span class="dc">amarillas</span> son don't cares.
La seccion <b>Terminos reutilizables</b> y el <b>Circuito completo sugerido</b>
muestran las compuertas que pueden compartirse entre salidas para ahorrar
componentes. Las ecuaciones salen tambien en varios lenguajes, con boton para
copiarlas.</p>
</div></details>
"""


def _comparison_section(table, solutions):
    names = list(table.outputs)
    if not names:
        return ""

    def tot(kind):
        g = lit = 0
        for nm in names:
            c = solutions[nm][kind].cost()
            g += c[0]
            lit += c[1]
        return g, lit

    data = [("Solo SOP", "sop"), ("Solo POS", "pos"), ("Mezcla (mejor por salida)", "best")]
    rows = [(label, tot(kind)) for label, kind in data]
    winner = min(rows, key=lambda r: r[1])[0]

    out = [
        "<h2>Comparativa de componentes</h2>",
        "<p class='hint'>Suma por salida (sin contar el ahorro de las compuertas compartidas, "
        "que se ve en el circuito combinado). Gana la estrategia con menos compuertas.</p>",
        "<table class='shared'><thead><tr><th>Estrategia</th><th>Compuertas</th>"
        "<th>Literales</th><th></th></tr></thead><tbody>",
    ]
    for label, (g, l) in rows:
        win = label == winner
        style = " style='background:#e9f5e9;font-weight:bold;'" if win else ""
        out.append(f"<tr{style}><td>{_esc(label)}</td><td>{g}</td><td>{l}</td>"
                   f"<td>{'&#9733; mejor' if win else ''}</td></tr>")
    out.append("</tbody></table>")

    det = ["<details class='guide'><summary>Ver todos los terminos (SOP y POS por salida)</summary>"
           "<div class='guidebody'>"]
    for nm in names:
        det.append(f"<p><b>{_esc(nm)}</b><br>SOP: <code>{_esc(solutions[nm]['sop'].equation)}</code>"
                   f"<br>POS: <code>{_esc(solutions[nm]['pos'].equation)}</code></p>")
    det.append("</div></details>")
    return "".join(out) + "".join(det)


def _languages_section(table, solutions, opt_langs):
    """Bloque por lenguaje con TODAS las salidas juntas (un copiar por lenguaje)."""
    if opt_langs is not None and len(opt_langs) == 0:
        return ""
    chosen = opt_langs or codegen.LANG_ORDER
    parts = ["<h2>Ecuaciones en varios lenguajes</h2>",
             "<p class='hint'>Cada bloque trae todas las salidas en ese lenguaje; el boton copia el bloque completo.</p>"]
    for lang in chosen:
        if lang not in codegen.OPS:
            continue
        lines = [codegen.render(solutions[name]["best"], name, lang) for name in table.outputs]
        blob = "\n".join(lines)
        parts.append("<div class='langblock'>")
        parts.append(
            f"<div class='langhead'>{_esc(lang)} "
            f"<button class='copybtn' data-clip=\"{_attr(blob)}\">copiar {_esc(lang)}</button></div>"
        )
        parts.append(f"<pre class='langpre'>{_esc(blob)}</pre>")
        parts.append("</div>")
    return "".join(parts)


def _kmap_for_form(vals, variables, sol, form):
    """Devuelve (label, patterns, form_real). XOR no agrupa: usa el SOP."""
    if form == "xor":
        s = sol["sop"]
        pats = s.patterns if s.const is None else []
        return "K-map (agrupado en SOP)", pats, "sop"
    if form in ("nand", "nor"):
        # el NAND se arma sobre los grupos del SOP, y el NOR sobre los del POS:
        # el mapa es el mismo, cambia la realizacion
        base = "sop" if form == "nand" else "pos"
        s = sol[base]
        pats = s.patterns if s.const is None else []
        return f"K-map {base.upper()} (base del {form.upper()})", pats, base
    s = sol[form]
    pats = s.patterns if s.const is None else []
    return f"K-map {form.upper()}", pats, form


def build_report(table, opt=None):
    opt = opt or Options()
    solutions = {
        name: solve_output(vals, table.variables)
        for name, vals in table.outputs.items()
    }

    body = [f"<h1>{_esc(opt.title)}</h1>"]
    body.append(
        f"<p class='meta'>{table.nvars} variables "
        f"({', '.join(table.variables)}) &middot; {len(table.outputs)} salida(s)</p>"
    )
    body.append(_GUIDE)

    if opt.table:
        body.append(
            "<h2>Tabla de verdad "
            f"<button class='copybtn' data-clip=\"{_attr(_table_tsv(table))}\">copiar tabla</button></h2>"
        )
        body.append(_truth_table_html(table))

    # terminos compartidos
    if opt.shared and len(table.outputs) > 1:
        sh = shared_terms(solutions, table.variables, "sop")
        if sh:
            body.append("<h2>Terminos reutilizables (SOP)</h2>")
            body.append("<table class='shared'><thead><tr>"
                        "<th>Termino (compuerta)</th><th>Usado en</th></tr></thead><tbody>")
            for d in sh:
                body.append(
                    f"<tr><td><code>{_esc(d['term'])}</code></td>"
                    f"<td>{', '.join(map(_esc, d['outputs']))}</td></tr>"
                )
            body.append("</tbody></table>")
            body.append("<p class='hint'>Estas compuertas pueden compartirse entre salidas "
                        "para ahorrar componentes.</p>")

    body.append(_comparison_section(table, solutions))

    # por salida
    for name, vals in table.outputs.items():
        sol = solutions[name]
        body.append("<div class='outcard'>")
        body.append(f"<h2>Salida <code>{_esc(name)}</code></h2>")

        # ecuaciones
        body.append("<div class='eqs'>")
        body.append(
            f"<div><b>SOP:</b> <code>{_esc(name)} = {_esc(sol['sop'].equation)}</code> "
            f"<span class='cost'>({sol['sop'].cost()[0]} comp, {sol['sop'].cost()[1]} lit)</span></div>"
        )
        body.append(
            f"<div><b>POS:</b> <code>{_esc(name)} = {_esc(sol['pos'].equation)}</code> "
            f"<span class='cost'>({sol['pos'].cost()[0]} comp, {sol['pos'].cost()[1]} lit)</span></div>"
        )
        if sol["xor"]:
            body.append(
                f"<div class='xor'>&#8853; <b>XOR/XNOR:</b> <code>{_esc(name)} = {_esc(sol['xor'].equation)}</code> "
                f"<span class='cost'>({sol['xor'].cost()[0]} comp, {sol['xor'].cost()[1]} lit)</span></div>"
            )
        body.append(
            f"<div class='best'>&#9733; Mejor por costo: <b>{sol['best'].form.upper()}</b> &rarr; "
            f"<code>{_esc(name)} = {_esc(sol['best'].equation)}</code></div>"
        )
        body.append("</div>")

        forms = _forms_to_show(opt, sol["best"])

        if opt.kmap:
            body.append("<div class='maps'>")
            seen_pats = set()
            for form in forms:
                label, pats, _ = _kmap_for_form(vals, table.variables, sol, form)
                key = (label, tuple(pats))
                if key in seen_pats:
                    continue
                seen_pats.add(key)
                body.append("<div class='mapwrap'>")
                body.append(f"<div class='maplabel'>{label}</div>")
                body.append(kmap.kmap_svg(vals, table.variables, pats))
                if pats:
                    body.append("<div class='legend'>"
                                + kmap.group_legend(pats, table.variables, "sop")
                                + "</div>")
                body.append("</div>")
            body.append("</div>")

        if opt.circuit:
            body.append("<div class='circuits'>")
            for form in forms:
                body.append("<div class='cwrap'>")
                body.append(f"<div class='maplabel'>Circuito {form.upper()}</div>")
                body.append(circuit.circuit_svg(sol[form], name))
                body.append("</div>")
            body.append("</div>")

        body.append("</div>")  # outcard

    # circuito completo combinado (SOP con compuertas compartidas)
    if opt.circuit and any(solutions[n]["sop"].const is None for n in table.outputs):
        named_sops = [(n, solutions[n]["sop"]) for n in table.outputs]
        svg, gates = circuit.build_shared_circuit(named_sops)
        body.append("<h2>Circuito completo sugerido</h2>")
        body.append("<p class='hint'>Realizacion en SOP de todas las salidas con las compuertas AND "
                    "compartidas (los atajos). Para una salida donde convenga XOR o POS, revisa su "
                    "circuito individual de arriba.</p>")
        if gates:
            body.append("<table class='shared'><thead><tr><th>Compuerta</th><th>Termino</th>"
                        "<th>Usada en</th></tr></thead><tbody>")
            for g in gates:
                mark = " (compartida)" if len(g["outputs"]) > 1 else ""
                body.append(
                    f"<tr><td><code>{_esc(g['id'])}</code></td>"
                    f"<td><code>{_esc(g['term'])}</code></td>"
                    f"<td>{', '.join(map(_esc, g['outputs']))}{mark}</td></tr>"
                )
            body.append("</tbody></table>")
        body.append("<div class='cwrap' style='overflow-x:auto;'>" + svg + "</div>")

    body.append(_languages_section(table, solutions, opt.langs))

    return _wrap_html(opt.title, "\n".join(body))


_CSS = """
body{font-family:Georgia,serif;margin:24px;color:#222;background:#fafafa;}
h1{font-size:24px;} h2{font-size:18px;border-bottom:1px solid #ccc;padding-bottom:3px;margin-top:26px;}
h3{font-size:15px;}
code{font-family:Consolas,monospace;background:#eef;padding:1px 4px;border-radius:3px;}
.meta{color:#666;}
table{border-collapse:collapse;margin:8px 0;}
.tt td,.tt th{border:1px solid #999;padding:3px 9px;text-align:center;font-size:13px;}
.tt th{background:#e8e8e8;}
.tt .idx{color:#888;} .tt .one{background:#e9f5e9;font-weight:bold;}
.tt .dc{background:#fff3cd;color:#b8860b;} .tt .note{text-align:left;font-style:italic;}
.shared td,.shared th{border:1px solid #aaa;padding:4px 10px;font-size:13px;}
.shared th{background:#e8e8e8;}
.eqs{background:#fff;border:1px solid #ddd;border-radius:6px;padding:10px;margin:8px 0;line-height:1.7;}
.cost{color:#888;font-size:12px;}
.best{margin-top:6px;color:#1a7a1a;}
.xor{color:#7a1a7a;}
.maps,.circuits{display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start;}
.mapwrap,.cwrap{background:#fff;border:1px solid #ddd;border-radius:6px;padding:10px;}
.maplabel{font-weight:bold;font-size:13px;margin-bottom:6px;}
.legend{margin-top:8px;font-size:12px;}
.outcard{margin-bottom:18px;}
.hint{color:#666;font-size:12px;font-style:italic;}
.guide{background:#eef4ff;border:1px solid #c8d8f0;border-radius:6px;padding:8px 12px;margin:10px 0;}
.guide summary{font-weight:bold;cursor:pointer;}
.guidebody{font-size:13px;line-height:1.6;}
.guidebody .dc{background:#fff3cd;color:#b8860b;padding:0 3px;border-radius:3px;}
.langhead{font-weight:bold;font-size:14px;margin:12px 0 4px;display:flex;
  align-items:center;gap:10px;}
.langblock{margin:6px 0 14px;}
.langpre{background:#f6f6f6;border:1px solid #ddd;border-radius:5px;padding:9px 11px;
  font-family:Consolas,monospace;font-size:13px;white-space:pre;overflow-x:auto;margin:0;}
.copybtn{font-size:11px;border:1px solid #aaa;background:#f3f3f3;border-radius:4px;
  padding:2px 8px;cursor:pointer;}
.copybtn:hover{background:#e2e8f5;}
"""

_CLIP_SCRIPT = """
<script>
document.addEventListener('click', function(e){
  var b = e.target.closest('.copybtn'); if(!b) return;
  navigator.clipboard.writeText(b.dataset.clip).then(function(){
    var t = b.textContent; b.textContent = 'copiado';
    setTimeout(function(){ b.textContent = t; }, 1200);
  });
});
</script>
"""


def _wrap_html(title, body):
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head>"
        f"<body>{body}{_CLIP_SCRIPT}</body></html>"
    )


def save_report(html, path=None, open_browser=False):
    if path is None:
        fd, path = tempfile.mkstemp(suffix=".html", prefix="ktool_")
        os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    if open_browser:
        webbrowser.open("file://" + os.path.abspath(path))
    return path
