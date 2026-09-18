"""CLI de ktool.

El comando es `ktool` (alias historico: `kmap`; ambos hacen lo mismo).

Ejemplos:
    ktool gui
    ktool -e "A'B + C" --open
    ktool -n 3 -m 1,4,5,6 -d 2,7
    ktool -n 3 --truth 01x011x1 --form both
    ktool -e "A^B^C" --text
    ktool -n 4 -m 0x1,0b11,5 --no-kmap --out salida.html
"""

from __future__ import annotations

import argparse
import sys

from .core import table
from .core.table import TruthTable
from .core.simplify import solve_output, shared_terms
from .render import codegen
from .render.report import Options, build_report, save_report

def _canon_lang(tok):
    canon = {name.lower(): name for name in codegen.LANG_ORDER}
    return canon.get(tok.lower()) or codegen.LANG_ALIASES.get(tok.lower())


def _resolve_langs(args):
    if args.no_langs:
        return []
    if not args.langs:
        return None
    out = []
    for tok in args.langs.replace(",", " ").split():
        name = _canon_lang(tok)
        if not name:
            print(f"aviso: lenguaje desconocido '{tok}' (ignorado)")
        elif name not in out:
            out.append(name)
    return out


def _build_parser():
    p = argparse.ArgumentParser(
        prog="ktool",
        description="Simplificador de logica digital: K-map, SOP/POS, compuertas y reuso de terminos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("gui", help="abre la interfaz grafica")

    # opciones de entrada (comando por defecto = resolver)
    p.add_argument("-n", "--vars", type=int,
                   help=f"numero de variables ({table.MIN_VARS}-{table.MAX_VARS})")
    p.add_argument("-e", "--expr", help="expresion booleana (ej: \"A'B + C\")")
    p.add_argument("-m", "--minterms", help="minterminos: dec, 0x.. hex o 0b.. bin")
    p.add_argument("-d", "--dontcares", help="don't cares (misma sintaxis)")
    p.add_argument("--truth", help="vector de salida, ej 01x011x1 (largo 2^n)")
    p.add_argument("--name", default="Y", help="nombre de la salida (default Y)")

    # control de salida
    p.add_argument("--form", choices=["sop", "pos", "auto", "both"], default="auto",
                   help="forma a mostrar (default auto = la mas barata)")
    p.add_argument("--no-kmap", action="store_true", help="no incluir mapas de Karnaugh")
    p.add_argument("--no-circuit", action="store_true", help="no incluir circuitos")
    p.add_argument("--no-table", action="store_true", help="no incluir tabla de verdad")
    p.add_argument("--gates-only", action="store_true", help="solo compuertas (sin K-map ni tabla)")
    p.add_argument("--langs", help="lenguajes a incluir, separados por coma (ej: verilog,c,vhdl)")
    p.add_argument("--no-langs", action="store_true", help="no incluir el bloque de ecuaciones por lenguaje")
    p.add_argument("--to", help="traducir la expresion -e directo a un lenguaje (ej: verilog) sin minimizar")
    p.add_argument("--text", action="store_true", help="solo imprimir ecuaciones en la terminal")
    p.add_argument("--out", help="ruta del documento HTML a generar")
    p.add_argument("--open", action="store_true", help="abrir el documento en el navegador")
    p.add_argument("--title", default="Resultados ktool", help="titulo del documento")
    return p


def _table_from_args(args):
    """Arma la tabla pedida. Cualquier entrada invalida sale como SystemExit
    con su motivo, nunca como un traceback."""
    if args.vars is not None:
        table.validar_nvars(args.vars)

    if args.expr:
        return TruthTable.from_expression(args.expr, nvars=args.vars, name=args.name)

    if args.truth is not None:
        vals = table.parse_truth_string(args.truth)
        if not vals:
            raise ValueError("el vector --truth esta vacio")
        n = (len(vals) - 1).bit_length()
        if 1 << n != len(vals):
            raise ValueError(
                f"el vector --truth tiene {len(vals)} valores; debe ser potencia de 2"
            )
        if args.vars and (1 << args.vars) != len(vals):
            raise ValueError(
                f"--vars {args.vars} no concuerda con --truth de largo {len(vals)} "
                f"(serian {n} variables)"
            )
        table.validar_nvars(n)
        return TruthTable(n, outputs={args.name: vals})

    if args.minterms is not None:
        if not args.vars:
            raise ValueError("usa -n/--vars con -m/--minterms")
        mins = table.parse_index_list(args.minterms)
        dcs = table.parse_index_list(args.dontcares) if args.dontcares else []
        return TruthTable.from_minterms(args.vars, mins, dcs, name=args.name)

    if args.dontcares is not None:
        raise ValueError("-d/--dontcares necesita -m/--minterms")

    raise ValueError("nada que resolver: usa -e, -m o --truth (o 'ktool gui'). Mira 'ktool -h'.")


def _print_text(table):
    print(f"# {table.nvars} variables: {', '.join(table.variables)}")
    sols = {n: solve_output(v, table.variables) for n, v in table.outputs.items()}
    for name, sol in sols.items():
        print(f"\n[{name}]")
        print(f"  SOP : {name} = {sol['sop'].equation}   ({sol['sop'].cost()[0]} comp, {sol['sop'].cost()[1]} lit)")
        print(f"  POS : {name} = {sol['pos'].equation}   ({sol['pos'].cost()[0]} comp, {sol['pos'].cost()[1]} lit)")
        print(f"  best: {sol['best'].form.upper()} -> {name} = {sol['best'].equation}")
        if sol["parity"]:
            print(f"  xor : {name} = {sol['parity']['equation']}")
    if len(table.outputs) > 1:
        sh = shared_terms(sols, table.variables, "sop")
        if sh:
            print("\n[terminos reutilizables (SOP)]")
            for d in sh:
                print(f"  {d['term']:<14} -> {', '.join(d['outputs'])}")


def main(argv=None):
    args = _build_parser().parse_args(argv)

    if args.cmd == "gui":
        from .gui import launch
        launch()
        return

    if args.to:
        if not args.expr:
            raise SystemExit("--to necesita una expresion con -e/--expr")
        lang = _canon_lang(args.to)
        if not lang:
            raise SystemExit(f"lenguaje desconocido para --to: '{args.to}'")
        try:
            print(codegen.translate(args.expr, args.name, lang))
        except ValueError as e:
            raise SystemExit(str(e))
        return

    try:
        table = _table_from_args(args)
    except ValueError as e:
        raise SystemExit(str(e))

    if args.text:
        _print_text(table)
        return

    if args.gates_only:
        args.no_kmap = True
        args.no_table = True

    opt = Options(
        form=args.form,
        kmap=not args.no_kmap,
        circuit=not args.no_circuit,
        table=not args.no_table,
        title=args.title,
        langs=_resolve_langs(args),
    )
    html = build_report(table, opt)
    open_it = args.open or (args.out is None)
    path = save_report(html, args.out, open_browser=open_it)
    print(f"documento generado: {path}")


if __name__ == "__main__":
    main()
