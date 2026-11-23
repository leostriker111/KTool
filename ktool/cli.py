"""CLI de ktool.

El comando es `ktool` (alias historico: `kmap`; ambos hacen lo mismo).

Ejemplos:
    ktool gui
    ktool -e "A'B + C" --open
    ktool -n 3 -m 1,4,5,6 -d 2,7
    ktool -n 3 --truth 01x011x1 --form both
    ktool -e "A^B^C" --text
    ktool -n 4 -m 0x1,0b11,5 --no-kmap --out salida.html

Kit de hardware (codigo para PIC, ESP32, Arduino, STM32, Pico, FPGA, GAL y 74LS):
    ktool -e "A'B + C" --hw kit
    ktool -n 4 -m 0,1,2,5 --form nand --hw kit_nand
    ktool -e "A'B + C" --hw kit --pines max2=26,28,33,73 --pines uno_nano=2,3,8,9
    ktool -e "A'B + C" --proto --kit-en-documento --out todo.html

Armado en protoboard (BETA):
    ktool -n 3 -m 1,4,5,6 -d 2,7 --proto --out salida.html
    ktool -n 3 -m 1,4,5,6 --proto --proto-extremos led --open
    ktool -n 4 -m 0,1,2,5 --proto --proto-modo forzado --proto-chips 7400,7404
    ktool -n 4 -m 0,1,2,5 --proto --form nand --proto-extremos 7seg_ca

Esta en beta: la lista de cables esta verificada contra la tabla de verdad,
pero nadie lo ha armado todavia en una mesa de verdad, la GUI aun no tiene los
botones, y en circuitos grandes el dibujo se enreda (issue #8). Ejemplos ya
generados en la carpeta ejemplos/ del repo.
"""

from __future__ import annotations

import argparse
import sys

from .core import table
from .core.table import TruthTable
from .core.simplify import solve_output, shared_terms
from .render import codegen
from .render.report import Options, build_report, save_report

_FSM_EPILOG = """\
Formato del .json (maquina de estados):

  {
    "name": "Mi maquina",
    "kind": "moore",                    # moore | mealy
    "inputs": ["X"],                    # [] = contador libre (solo reloj)
    "state_bits": ["Q2", "Q1", "Q0"],   # flip-flops, el primero es el bit alto
    "outputs": ["a","b","c","d","e","f","g"],
    "states": [
      {"name": "S7", "code": "111", "label": "R", "out": "0000101"}
    ],
    "transitions": [
      {"from": "S7", "in": "0", "to": "S6"}
    ]
  }

  code = el codigo binario del estado    out = su salida (Moore)
  in   = los bits de entrada ("" si no hay)

Ejemplos en la carpeta ejemplos/ del repositorio:
    ktool fsm ejemplos/letrero_tool/maquina.json --ff T --vhdl vhdl_letrero
"""

_CONTADOR_EPILOG = """\
Ejemplos (los de la practica de Circuitos Secuenciales):
    ktool contador --mod 13 --baja
    ktool contador --secuencia 4,7,2,6,0,3,5,1 --entradas X --modo 0=sigue --modo 1=paro
    ktool contador --entradas X,Y --modo 00=0-15 --modo 01=paro --modo 10=reinicio ^
                   --modo 11=15,12,9,6,3,0 --ff JK --vhdl vhdl_mod16

Cada modo: una lista (4,7,2), un rango (0-15 sube, 12-0 baja), 'paro' (se queda),
'reinicio' (al primer numero), 'set' (todos los flip-flops a 1) o 'sigue' (la
--secuencia o el --mod). Si un modo arranca desde un numero que no esta en su
lista, salta al primero de esa lista.
"""


def _opciones_secuenciales(sp):
    """Las opciones que comparten 'fsm' y 'contador'."""
    sp.add_argument("--ff", default="D", help="flip-flop: D, T, JK o SR (por omision D)")
    sp.add_argument("--form", choices=["sop", "pos", "auto", "both"], default="auto",
                    help="forma de las ecuaciones (auto = la mas barata)")
    sp.add_argument("--out", help="ruta del documento HTML")
    sp.add_argument("--no-open", action="store_true", help="no abrir el navegador")
    sp.add_argument("--no-circuit", action="store_true", help="no dibujar circuitos")
    sp.add_argument("--langs", help="lenguajes a incluir (ej: verilog,vhdl)")
    sp.add_argument("--no-langs", action="store_true", help="omitir el bloque de lenguajes")
    sp.add_argument("--title", help="titulo del documento")
    sp.add_argument("--vhdl", metavar="CARPETA",
                    help="escribir el VHDL por los 3 metodos y su banco de prueba")


def _maquina_de_contador(args):
    """Los argumentos de `ktool contador` -> el dict de la maquina."""
    from .fsm import contadores
    base = None
    if args.secuencia:
        base = [int(x) for x in args.secuencia.replace(" ", "").split(",") if x]
    elif args.mod:
        base = (contadores.descendente(args.mod) if args.baja
                else contadores.ascendente(args.mod))
    entradas = [e.strip() for e in (args.entradas or "").split(",") if e.strip()]
    if not entradas:
        if base is None:
            raise ValueError("di que cuenta: --mod N o --secuencia 4,7,2...")
        modos = {"": base}
    else:
        modos = {}
        for pedido in args.modo or []:
            combo, _, que = pedido.partition("=")
            combo = combo.strip()
            if len(combo) != len(entradas) or set(combo) - {"0", "1"}:
                raise ValueError(f"--modo {pedido!r}: la combinacion debe tener "
                                 f"{len(entradas)} bits (uno por entrada: {', '.join(entradas)})")
            modos[combo] = contadores.leer_modo(que, base)
    titulo = args.titulo or ("Contador " + (f"mod-{args.mod}" if args.mod else "con secuencia"))
    return contadores.contador(titulo, modos, entradas, bits=args.bits)


def _correr_secuencial(args, fuente):
    """Documento (y VHDL si se pide) de una maquina ya armada como dict."""
    from .fsm import Machine
    from .hw import vhdl_fsm
    from .render.fsm_report import build_fsm_report, save_report
    try:
        maquina = Machine.from_dict(fuente)
        html = build_fsm_report(maquina, ff_kind=args.ff, title=args.title,
                                langs=_resolve_langs(args), circuit_on=not args.no_circuit,
                                form=args.form, fuente=fuente)
        if args.vhdl:
            nombres = vhdl_fsm.escribir(fuente, args.vhdl, args.ff)
    except (ValueError, KeyError) as e:
        raise SystemExit(f"maquina invalida: {e}")
    ruta = save_report(html, args.out, open_browser=not args.no_open)
    print(f"documento generado: {ruta}")
    if args.vhdl:
        print(f"VHDL en {args.vhdl}: {', '.join(nombres)}")


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

    # maquinas de estado
    fsm = sub.add_parser("fsm", help="disena una maquina de estados desde un .json",
                         formatter_class=argparse.RawDescriptionHelpFormatter,
                         epilog=_FSM_EPILOG)
    fsm.add_argument("archivo", help="el .json de la maquina (estados y transiciones)")
    _opciones_secuenciales(fsm)

    cont = sub.add_parser("contador", help="disena un contador sincrono",
                          formatter_class=argparse.RawDescriptionHelpFormatter,
                          epilog=_CONTADOR_EPILOG)
    cont.add_argument("--mod", type=int, help="modulo: cuenta de 0 a mod-1")
    cont.add_argument("--baja", action="store_true", help="con --mod: cuenta hacia abajo")
    cont.add_argument("--secuencia", help="la secuencia a recorrer, ej. 4,7,2,6,0,3,5,1")
    cont.add_argument("--entradas", help="entradas de control, ej. X,Y")
    cont.add_argument("--modo", action="append", metavar="COMBO=QUE",
                      help="que hace con cada combinacion de entradas (se repite): "
                           "00=0-15, 01=paro, 10=reinicio, 11=set, o una lista 15,12,9")
    cont.add_argument("--bits", type=int, help="cuantos flip-flops (por omision, los justos)")
    cont.add_argument("--titulo", help="el nombre del contador")
    cont.add_argument("--json", metavar="RUTA", help="guardar la maquina como .json")
    _opciones_secuenciales(cont)

    rel = sub.add_parser("reloj", help="divisor de frecuencia o 555 astable (calculadora)")
    rel.add_argument("--entrada", default="50M",
                     help="reloj de entrada en Hz, acepta prefijos: 50M, 16M, 1k (por omision 50M)")
    rel.add_argument("--salida", help="frecuencia que se quiere, en Hz (ej. 1, 0.5, 2k)")
    rel.add_argument("--periodo", help="o el periodo que se quiere, en segundos (ej. 3)")
    rel.add_argument("--ciclo", type=float, default=50, help="ciclo de trabajo en %% (por omision 50)")
    rel.add_argument("--codigo", choices=["vhdl", "c", "asm", "arduino"],
                     help="ademas, imprime el calculo escrito como codigo para ese hardware")
    rel.add_argument("--555", dest="astable", action="store_true",
                     help="en vez del divisor, R1, R2 y C de un 555 astable para --salida")

    # opciones de entrada (comando por defecto = resolver)
    p.add_argument("-n", "--vars", type=int,
                   help=f"numero de variables ({table.MIN_VARS}-{table.MAX_VARS})")
    p.add_argument("-e", "--expr", help="expresion booleana (ej: \"A'B + C\")")
    p.add_argument("-m", "--minterms", help="minterminos: dec, 0x.. hex o 0b.. bin")
    p.add_argument("-d", "--dontcares", help="don't cares (misma sintaxis)")
    p.add_argument("--truth", help="vector de salida, ej 01x011x1 (largo 2^n)")
    p.add_argument("--name", default="Y", help="nombre de la salida (default Y)")

    # control de salida
    p.add_argument("--form", choices=["sop", "pos", "nand", "nor", "auto", "both"],
                   default="auto",
                   help="forma a mostrar: sop, pos, nand (solo NAND), nor (solo NOR), "
                        "auto (la mas barata) o both")
    p.add_argument("--no-kmap", action="store_true", help="no incluir mapas de Karnaugh")
    p.add_argument("--no-circuit", action="store_true", help="no incluir circuitos")
    p.add_argument("--no-table", action="store_true", help="no incluir tabla de verdad")
    p.add_argument("--gates-only", action="store_true", help="solo compuertas (sin K-map ni tabla)")
    p.add_argument("--langs", help="lenguajes a incluir, separados por coma (ej: verilog,c,vhdl)")
    p.add_argument("--no-langs", action="store_true", help="no incluir el bloque de ecuaciones por lenguaje")
    p.add_argument("--to", help="traducir la expresion -e directo a un lenguaje (ej: verilog) sin minimizar")
    # protoboard
    p.add_argument("--proto", action="store_true",
                   help="[BETA] incluir el armado en protoboard: chips, tablero y "
                        "lista de cables")
    p.add_argument("--proto-modo", choices=["fiel", "forzado", "automatico"],
                   default="fiel",
                   help="como elegir los chips: fiel al diagrama, forzado a --proto-chips, "
                        "o automatico al ancho mayor")
    p.add_argument("--proto-chips",
                   help="chips permitidos para --proto-modo forzado (ej: 7400,7404)")
    p.add_argument("--proto-color-salidas", metavar="COLOR",
                   help="color de los cables de salida: 'arcoiris' (default), un "
                        "nombre (red, blue, ...) o un hex (#1f77b4)")
    p.add_argument("--proto-separado", action="store_true",
                   help="una protoboard por salida, en vez de una sola con todo")
    p.add_argument("--proto-extremos",
                   choices=["puntos", "led", "7seg_cc", "7seg_ca", "16seg_cc", "16seg_ca"],
                   default="puntos",
                   help="que se conecta en las salidas (cc = catodo comun, ca = anodo comun)")
    # kit de hardware
    p.add_argument("--hw", metavar="CARPETA",
                   help="generar el kit de hardware en CARPETA: codigo para PIC, ESP32, "
                        "Arduino, STM32, Pico, VHDL/Verilog con banco de prueba, MAX II, "
                        "GAL22V10, chips 74LS y una simulacion en Python")
    p.add_argument("--pines", metavar="PLACA=LISTA", action="append",
                   help="con --hw o --kit-en-documento: los pines de una placa, primero las "
                        "entradas y luego las salidas (ej: max2=26,28,33,73 o "
                        "uno_nano=2,3,8). Se repite para varias placas. Para placas con "
                        "LEDs o botones en pines fijos")
    p.add_argument("--max2-pines", metavar="LISTA",
                   help="atajo de --pines max2=LISTA")
    p.add_argument("--kit-en-documento", action="store_true",
                   help="incluir en el documento HTML el kit de hardware: la tabla de "
                        "pines y el codigo de cada placa")
    p.add_argument("--text", action="store_true", help="solo imprimir ecuaciones en la terminal")
    p.add_argument("--out", help="ruta del documento HTML a generar")
    p.add_argument("--open", action="store_true", help="abrir el documento en el navegador")
    p.add_argument("--title", default="Resultados ktool", help="titulo del documento")
    p.add_argument("--agregar-al-path", action="store_true",
                   help="(Windows) si instalaste con pip y 'ktool' no se reconoce: agrega "
                        "la carpeta de ktool.exe al PATH. Correlo como: "
                        "python -m ktool --agregar-al-path")
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
        for forma in ("nand", "nor"):
            s = sol[forma]
            print(f"  {forma.upper():<4}: {name} = {s.equation}   "
                  f"({s.cost()[0]} comp, {s.cost()[1]} lit)")
        print(f"  best: {sol['best'].form.upper()} -> {name} = {sol['best'].equation}")
        if sol["parity"]:
            print(f"  xor : {name} = {sol['parity']['equation']}")
    if len(table.outputs) > 1:
        sh = shared_terms(sols, table.variables, "sop")
        if sh:
            print("\n[terminos reutilizables (SOP)]")
            for d in sh:
                print(f"  {d['term']:<14} -> {', '.join(d['outputs'])}")


def _pines_de_args(args):
    """--pines PLACA=LISTA (repetible) y --max2-pines -> {placa: [pines]}."""
    from .hw import placas
    from .hw.modelo import leer_pines
    pedidos = list(args.pines or [])
    if args.max2_pines:
        pedidos.append("max2=" + args.max2_pines)
    pines = {}
    for pedido in pedidos:
        nombre, _, lista = pedido.partition("=")
        nombre = nombre.strip().lower()
        if not lista.strip():
            raise ValueError(f"--pines va como PLACA=LISTA, ej. max2=26,28,33: {pedido!r}")
        if nombre not in placas.PLACAS_CON_PINES:
            raise ValueError(f"no conozco la placa {nombre!r}. Las que aceptan pines: "
                             + ", ".join(placas.PLACAS_CON_PINES))
        pines[nombre] = leer_pines(lista, placas.PLACAS_CON_PINES[nombre])
    return pines


def _generar_kit(table, carpeta, forma, pines):
    """Escribe el kit y dice, plataforma por plataforma, que salio y que no."""
    from .hw import kit
    try:
        resumen = kit.generar(table, carpeta, forma, pines)
    except ValueError as e:
        raise SystemExit(str(e))
    print(f"kit de hardware en: {carpeta}")
    for plataforma, estado, detalle in resumen:
        marca = "  ok " if estado == "listo" else "  -- "
        print(f"{marca}{plataforma}")
        if estado != "listo":
            print(f"       {detalle}")
    print(f"resumen completo en {carpeta}/LEEME.md")


def _correr_reloj(args):
    """`ktool reloj`: los mismos datos que Herramientas > Calculadora de frecuencia."""
    from .gui.calculadora import leer_numero
    from .hw import reloj

    if args.astable:
        if not args.salida:
            raise ValueError("--555 necesita --salida (la frecuencia del 555)")
        r = reloj.astable_555_para(leer_numero(args.salida))
        for etiqueta, valor, unidad in (("R1", r["r1"], "Ohm"), ("R2", r["r2"], "Ohm"),
                                        ("C", r["c"], "F"), ("Frecuencia real", r["f"], "Hz"),
                                        ("Error", r["error_pct"], "%"),
                                        ("Periodo (T)", r["periodo"], "s"),
                                        ("Tiempo en alto", r["t_alto"], "s"),
                                        ("Tiempo en bajo", r["t_bajo"], "s"),
                                        ("Ciclo de trabajo", r["ciclo"], "%")):
            print(f"{etiqueta:<22} {reloj.formato(valor, unidad)}")
        return
    f_entrada = leer_numero(args.entrada)
    if args.periodo:
        calculo = reloj.calcular(f_entrada, periodo=leer_numero(args.periodo), ciclo=args.ciclo)
    elif args.salida:
        calculo = reloj.calcular(f_entrada, f_salida=leer_numero(args.salida), ciclo=args.ciclo)
    else:
        raise ValueError("falta --salida o --periodo")
    for etiqueta, legible, _copia in calculo.renglones():
        print(f"{etiqueta:<22} {legible}")
    if args.codigo == "vhdl":
        print("\n" + reloj.vhdl_divisor(f_entrada, calculo.f_real))
    elif args.codigo == "c":
        partes = reloj.c_pic18_retardo(f_entrada, calculo.f_real)
        for clave in ("definiciones", "configurar", "esperar_medio_periodo"):
            print("\n" + partes[clave])
    elif args.codigo == "asm":
        print("\n" + reloj.asm_pic18_retardo(f_entrada, calculo.t_alto))
    elif args.codigo == "arduino":
        partes = reloj.arduino_retardo(calculo.f_real)
        for clave in ("variables", "setup", "en_loop"):
            print("\n" + partes[clave])


def main(argv=None):
    args = _build_parser().parse_args(argv)

    if args.agregar_al_path:
        from .ruta import agregar_al_path
        raise SystemExit(agregar_al_path())

    if args.cmd == "fsm":
        import json
        try:
            with open(args.archivo, encoding="utf-8") as f:
                fuente = json.load(f)
        except FileNotFoundError:
            raise SystemExit(f"no se encontro el archivo: {args.archivo}")
        except ValueError as e:
            raise SystemExit(f"el archivo no es un JSON valido: {e}")
        _correr_secuencial(args, fuente)
        return

    if args.cmd == "contador":
        try:
            fuente = _maquina_de_contador(args)
        except ValueError as e:
            raise SystemExit(str(e))
        if args.json:
            from . import io as ktio
            ktio.save(dict(fuente, doc_type="fsm", ff=args.ff), args.json)
            print(f"maquina guardada en {args.json}")
        _correr_secuencial(args, fuente)
        return

    if args.cmd == "reloj":
        try:
            _correr_reloj(args)
        except ValueError as e:
            raise SystemExit(str(e))
        return

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

    if args.proto_chips:
        from .proto import chips as _chips
        for nombre in args.proto_chips.replace(",", " ").split():
            if nombre.strip() not in _chips.CHIPS:
                raise SystemExit(
                    f"el chip {nombre.strip()!r} no esta en el catalogo. "
                    f"Hay: {', '.join(sorted(_chips.CHIPS))}")
    if args.proto_modo == "forzado" and not args.proto_chips:
        raise SystemExit("--proto-modo forzado necesita --proto-chips")

    try:
        table = _table_from_args(args)
    except ValueError as e:
        raise SystemExit(str(e))

    try:
        pines = _pines_de_args(args)
    except ValueError as e:
        raise SystemExit(str(e))
    if args.hw:
        _generar_kit(table, args.hw, args.form, pines)
        return
    if pines and not args.kit_en_documento:
        raise SystemExit("--pines y --max2-pines van con --hw o con --kit-en-documento")

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
        proto=args.proto,
        proto_modo=args.proto_modo,
        proto_chips=([s.strip() for s in args.proto_chips.replace(",", " ").split()]
                     if args.proto_chips else None),
        proto_extremos=args.proto_extremos,
        proto_separado=args.proto_separado,
        proto_color_salidas=args.proto_color_salidas,
        kit=args.kit_en_documento,
        kit_pines=pines,
    )
    try:
        html = build_report(table, opt)
    except ValueError as e:   # un pin o un nombre que no sirve para el kit
        raise SystemExit(str(e))
    open_it = args.open or (args.out is None)
    path = save_report(html, args.out, open_browser=open_it)
    print(f"documento generado: {path}")


if __name__ == "__main__":
    main()
