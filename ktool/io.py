"""Archivo fuente de ktool: guardar/abrir el estado de trabajo en JSON.

El HTML es la salida; este modulo guarda la ENTRADA (lo que lo genero) para
poder recuperarla, reabrirla o regenerarla con otras opciones.

Diseño generico y retrocompatible:
- El fuente es un diccionario. Cada subsistema mete su seccion con su propia
  clave; agregar una funcion nueva es agregar una clave mas, nada se rompe.
- Al leer SIEMPRE se usan defaults (`.get`) para las claves que falten, asi los
  archivos viejos siguen abriendo cuando el formato crece.
- `ktool_format` se sube solo si algun dia hay un cambio que rompa; mientras tanto
  los lectores nuevos abren todos los formatos anteriores.
"""

from __future__ import annotations

import json

from . import __version__

FORMAT = 1
EXT = ".ktool.json"


def stamp(source):
    """Agrega la metadata de ktool sin pisar lo que ya traiga el dict."""
    out = dict(source)
    out.setdefault("ktool_format", FORMAT)
    out["ktool_version"] = __version__
    return out


def save(source, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stamp(source), f, ensure_ascii=False, indent=2)
    return path


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def doc_type(source):
    """'table' (tabla combinacional) o 'fsm' (maquina de estados).

    Detecta tambien los archivos viejos de maquina (sin doc_type) por su forma."""
    t = source.get("doc_type")
    if t:
        return t
    if "state_bits" in source or "transitions" in source:
        return "fsm"
    return "table"
