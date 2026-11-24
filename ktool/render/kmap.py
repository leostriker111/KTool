"""Render del K-map a SVG con grupos circulados en colores."""

from __future__ import annotations

from ..core import kmap_layout
from ._util import _esc

from .. import theme

CELL = 48


def _bits_label(gray_code, var_positions, variables):
    k = len(var_positions)
    bits = "".join(str((gray_code >> (k - 1 - i)) & 1) for i in range(k))
    return bits


def _screen_runs(indices):
    s = sorted(indices)
    runs = []
    for x in s:
        if runs and x == runs[-1][-1] + 1:
            runs[-1].append(x)
        else:
            runs.append([x])
    return runs





def kmap_svg(values, variables, patterns=None, title=None):
    n = len(variables)
    row_vars, col_vars, nrows, ncols = kmap_layout.kmap_layout(n)
    patterns = patterns or []

    left = 78
    top = 56
    # la esquina 'Q1 Q0\B T C PEA' es larga con 5-6 variables: ensanchar a la izquierda
    _esq = sum(len(variables[i]) for i in range(n)) * 8 + 4 * 7 + 22
    left = max(left, _esq)
    width = left + ncols * CELL + 20
    height = top + nrows * CELL + 20

    # con nombres largos (SEL, D0) las etiquetas van separadas: 'SEL D0', no 'SELD0'
    pegado = " " if any(len(v) > 1 for v in variables) else ""
    row_label = pegado.join(variables[i] for i in row_vars)
    col_label = pegado.join(variables[i] for i in col_vars)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="Georgia, serif">'
    ]
    if title:
        out.append(
            f'<text x="{left}" y="20" font-size="15" font-weight="bold">{_esc(title)}</text>'
        )

    # encabezados de variables
    out.append(
        f'<text x="{left - 8}" y="{top - 8}" font-size="13" font-style="italic" text-anchor="end">'
        f'{_esc(row_label)}\\{_esc(col_label)}</text>'
    )
    # encabezados de columnas (gray)
    for c in range(ncols):
        lbl = _bits_label(kmap_layout.gray(c), col_vars, variables)
        x = left + c * CELL + CELL / 2
        out.append(
            f'<text x="{x}" y="{top - 8}" font-size="13" text-anchor="middle">{lbl}</text>'
        )
    # encabezados de filas (gray)
    for r in range(nrows):
        lbl = _bits_label(kmap_layout.gray(r), row_vars, variables)
        y = top + r * CELL + CELL / 2 + 4
        out.append(
            f'<text x="{left - 10}" y="{y}" font-size="13" text-anchor="end">{lbl}</text>'
        )

    # celdas
    for r in range(nrows):
        for c in range(ncols):
            idx = kmap_layout.cell_index(r, c, n)
            v = values[idx]
            x = left + c * CELL
            y = top + r * CELL
            fill = "#ffffff"
            if v == "x":
                fill = "#fff3cd"
            elif v == 1:
                fill = "#e9f5e9"
            out.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                f'fill="{fill}" stroke="#888" stroke-width="1"/>'
            )
            txt = "x" if v == "x" else str(v)
            color = "#b8860b" if v == "x" else "#222"
            out.append(
                f'<text x="{x + CELL/2}" y="{y + CELL/2 + 5}" font-size="16" '
                f'text-anchor="middle" fill="{color}">{txt}</text>'
            )
            out.append(
                f'<text x="{x + 4}" y="{y + 13}" font-size="9" fill="#aaa">{idx}</text>'
            )

    # grupos
    for gi, pat in enumerate(patterns):
        color = theme.GROUP_COLORS[gi % len(theme.GROUP_COLORS)]
        inset = 4 + (gi % 4) * 3
        rowset = [r for r in range(nrows) if kmap_layout.pattern_matches_row(pat, r, n)]
        colset = [c for c in range(ncols) if kmap_layout.pattern_matches_col(pat, c, n)]
        for rr in _screen_runs(rowset):
            for cc in _screen_runs(colset):
                x = left + cc[0] * CELL + inset
                y = top + rr[0] * CELL + inset
                w = len(cc) * CELL - 2 * inset
                h = len(rr) * CELL - 2 * inset
                out.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" ry="14" '
                    f'fill="none" stroke="{color}" stroke-width="2.5" opacity="0.9"/>'
                )

    out.append("</svg>")
    return "\n".join(out)


def group_legend(patterns, variables, form="sop"):
    """HTML con el color de cada grupo y su termino."""
    from ..core.simplify import format_product, format_sum

    rows = []
    for gi, pat in enumerate(patterns):
        color = theme.GROUP_COLORS[gi % len(theme.GROUP_COLORS)]
        term = format_product(pat, variables) if form == "sop" else format_sum(pat, variables)
        rows.append(
            f'<div style="display:flex;align-items:center;gap:8px;margin:2px 0;">'
            f'<span style="width:16px;height:16px;border-radius:4px;background:{color};'
            f'display:inline-block;"></span><code>{_esc(term)}</code></div>'
        )
    return "".join(rows)
