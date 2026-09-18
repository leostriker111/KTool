"""Saca el pinout DIP de un datasheet de TI, y lo comprueba contra si mismo.

La hoja trae la misma informacion dos veces: el dibujo del encapsulado y la
tabla "Pin Functions". Se leen por separado y se exige que coincidan. Si no
coinciden, o si falta una de las dos, no se adivina: falla y se reporta.

Ademas se aplica la convencion de la serie 74xx --GND en el pin n/2, VCC en el
pin n-- para quedarse con el DIP entre los varios encapsulados de la hoja.
"""
import re
import sys

import pypdf

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def texto(pdf, hasta=6):
    r = pypdf.PdfReader(pdf)
    return "\n".join((r.pages[p].extract_text() or "")
                     for p in range(min(len(r.pages), hasta)))


def _limpia(nombre):
    """'V CC' -> 'VCC'. Los subindices salen separados."""
    return re.sub(r"\s+", "", nombre).upper()


def del_dibujo(txt, pines):
    """Bloques del dibujo: lineas '<pin><nombre>  <pin> <nombre>'."""
    salida = []
    lineas = [l.strip() for l in txt.splitlines()]
    for i in range(len(lineas)):
        mapa = {}
        ok = True
        for k in range(pines // 2):
            if i + k >= len(lineas):
                ok = False
                break
            esperado = str(k + 1)
            l = lineas[i + k]
            if not l.startswith(esperado):
                ok = False
                break
            resto = l[len(esperado):]
            m = re.match(r"^\s*(.+?)\s+(\d+)\s*(.+)$", resto)
            if not m:
                ok = False
                break
            izq, der_num, der = m.group(1), int(m.group(2)), m.group(3)
            if der_num != pines - k:
                ok = False
                break
            mapa[k + 1] = _limpia(izq)
            mapa[der_num] = _limpia(der)
        if ok and len(mapa) == pines:
            salida.append(mapa)
    return salida


def de_la_tabla(txt, pines):
    """Tabla Pin Functions: 'NOMBRE  n [n...]  I/O  descripcion'."""
    mapa = {}
    for l in txt.splitlines():
        m = re.match(r"^([A-Z0-9/]{1,6})\s+(\d{1,2})(?:\s+(?:\d{1,2}|—|-)){0,4}\s+"
                     r"(I|O|I/O|G|P|—)\s", l.strip())
        if not m:
            continue
        nombre, pin = _limpia(m.group(1)), int(m.group(2))
        if 1 <= pin <= pines and pin not in mapa:
            mapa[pin] = nombre
    return mapa


def convencion(mapa, pines):
    return mapa.get(pines // 2) == "GND" and mapa.get(pines) == "VCC"


# ------------------------------------------------- lector 3: dibujo vectorial
#
# Las hojas viejas no traen tabla: el pinout es un dibujo, y el texto plano sale
# desordenado. Se toma cada etiqueta con su (x, y), se arman las filas del
# encapsulado (dos etiquetas a la misma altura) y se numeran por la convencion.

_NOMBRE = re.compile(r"^(VCC|GND|NC|[0-9]?[A-Z]{1,5}[0-9]?|[A-Z][0-9])$")


def _etiquetas(pdf, pagina):
    partes = []

    def visitor(texto_, cm, tm, fuente, tam):
        s = texto_.strip()
        if s:
            partes.append((round(tm[4], 1), round(tm[5], 1), s))

    pypdf.PdfReader(pdf).pages[pagina].extract_text(visitor_text=visitor)
    return partes


def _filas(cand, tol=2.5):
    porY = {}
    for x, y, s in cand:
        clave = next((k for k in porY if abs(k - y) <= tol), y)
        porY.setdefault(clave, []).append((x, s))
    filas = []
    for y, items in porY.items():
        if len(items) == 2:
            items.sort()
            filas.append((y, items[0][1], items[1][1]))
    filas.sort(key=lambda f: -f[0])
    return filas


def _pega_fragmentos(partes, dy=1.5, dx=9.0):
    """'V' + 'CC' -> 'VCC'. Los subindices salen como texto aparte."""
    partes = sorted(partes, key=lambda p: (-p[1], p[0]))
    salida = []
    for x, y, s in partes:
        if salida:
            px, py, ps = salida[-1]
            if abs(py - y) <= dy and 0 <= x - px <= dx:
                salida[-1] = (px, py, ps + s)
                continue
        salida.append((x, y, s))
    return salida


def del_vectorial(pdf, pines, paginas=3):
    salida = []
    lector = pypdf.PdfReader(pdf)
    for pagina in range(min(len(lector.pages), paginas)):
        # solo fragmentos cortos en mayusculas: si se pega texto corrido,
        # se destruyen etiquetas buenas al juntarlas con lo de al lado
        trozos = [(x, y, s) for x, y, s in _etiquetas(pdf, pagina)
                  if re.match(r"^[A-Z0-9]{1,6}$", s)]
        cand = [(x, y, s) for x, y, s in _pega_fragmentos(trozos) if _NOMBRE.match(s)]
        filas = _filas(cand)
        for i in range(max(0, len(filas) - pines // 2 + 1)):
            bloque = filas[i:i + pines // 2]
            if len(bloque) < pines // 2:
                continue
            pasos = [bloque[j][0] - bloque[j + 1][0] for j in range(len(bloque) - 1)]
            if not pasos or max(pasos) - min(pasos) > 3:
                continue
            mapa = {}
            for k, (_, izq, der) in enumerate(bloque):
                mapa[k + 1] = _limpia(izq)
                mapa[pines - k] = _limpia(der)
            if convencion(mapa, pines):
                salida.append(mapa)
    return salida


def pinout(pdf, pines=14):
    """Devuelve (mapa, nota). La nota dice cuantas lecturas independientes
    coincidieron; si dos se contradicen, no devuelve nada."""
    txt = texto(pdf)
    fuentes = {}

    dibujos = [d for d in del_dibujo(txt, pines) if convencion(d, pines)]
    if dibujos:
        fuentes["dibujo"] = dibujos[0]

    tabla = de_la_tabla(txt, pines)
    if tabla:
        tabla.setdefault(pines // 2, "GND")
        tabla.setdefault(pines, "VCC")
        if len(tabla) == pines and convencion(tabla, pines):
            fuentes["tabla"] = tabla

    vect = del_vectorial(pdf, pines)
    if vect:
        fuentes["vectorial"] = vect[0]

    if not fuentes:
        return None, "no se pudo leer el pinout"

    valores = list(fuentes.values())
    if any(v != valores[0] for v in valores[1:]):
        detalle = "; ".join(f"{k}={sorted(v.items())}" for k, v in fuentes.items())
        return None, "las lecturas NO coinciden -> " + detalle
    return valores[0], f"{len(fuentes)} lectura(s) coinciden: {', '.join(sorted(fuentes))}"


if __name__ == "__main__":
    ruta = sys.argv[1]
    pines = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    m, nota = pinout(ruta, pines)
    print("  ", nota)
    if m:
        print("   " + "  ".join(f"{p}:{m[p]}" for p in sorted(m)))
