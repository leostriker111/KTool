"""La configuracion del kit: que placas, con que pines, con que ajustes.

Es lo que el usuario decide en la ventana del kit, guardado aparte del circuito
para que tres lugares lean lo mismo:

    la ventana del kit      la edita (placas, pin planner, ajustes, archivos)
    Escribir kit / Generar  arma los archivos con ella (hw/kit.py)
    el documento            la imprime: placas, pines, ajustes y codigo

Asi, aunque el kit se escriba primero como archivos sueltos y el documento se
genere despues, el documento describe exactamente lo que se grabo.
"""

from __future__ import annotations

import json
import os

from . import ajustes as hw_ajustes
from . import kit as hw_kit
from . import placas

# Lo que se elige de entrada: las tres placas de las practicas y la simulacion
# en Python para revisar antes de grabar.
ELEGIDAS_DE_ENTRADA = ["pic18f45k50", "max2", "uno_nano", "python"]


class ConfigKit:
    """Todo lo que el usuario fijo para el kit.

    elegidas  claves de kit.PLATAFORMAS, en el orden de esa lista
    pines     {placa: {senal: pin}} del planificador (o la lista vieja de --pines)
    ajustes   {placa: {ajuste: valor}} (hw/ajustes.py)
    editados  {ruta: texto} archivos corregidos a mano en la vista previa
    carpeta   donde se escribe
    """

    def __init__(self):
        self.elegidas = list(ELEGIDAS_DE_ENTRADA)
        self.pines = {}
        self.ajustes = {}
        self.editados = {}
        self.carpeta = os.path.join(os.path.expanduser("~"), "Documents", "ktool_kit")

    # ---------------------------------------------------------------- uso
    def elegir(self, placa, si):
        """Palomea o despalomea una plataforma, conservando el orden del kit."""
        actuales = set(self.elegidas)
        if si:
            actuales.add(placa)
        else:
            actuales.discard(placa)
        self.elegidas = [clave for clave, _t in hw_kit.PLATAFORMAS if clave in actuales]

    def valores(self, placa):
        """Los ajustes completos de una placa (lo del usuario y, lo demas, de omision)."""
        return hw_ajustes.con_omision(placa, self.ajustes.get(placa))

    def armar(self, tabla, forma="auto"):
        """El Kit en memoria con esta configuracion. ValueError si un pin no sirve."""
        kit = hw_kit.armar(tabla, forma, pines=self._pines_validos(), elegidas=self.elegidas,
                           ajustes_por_placa=self.ajustes, editados=self.editados)
        self.anotar(kit)
        return kit

    def anotar(self, kit, secuencial=False):
        """Deja la configuracion dentro del kit: una seccion en su LEEME.md y el
        archivo configuracion.json.

        Asi una carpeta escrita con 'Escribir kit' dice por si sola con que
        ajustes se genero, aunque el documento se haga despues o no se haga."""
        lineas = ["", "## Configuracion", ""]
        for titulo, renglones in self.resumen_ajustes(secuencial):
            lineas.append(f"**{titulo}**")
            lineas.append("")
            for etiqueta, valor in renglones:
                lineas.append(f"- {etiqueta}: {valor}")
            lineas.append("")
        if self.editados:
            lineas.append("Archivos corregidos a mano: "
                          + ", ".join(sorted(r for r in self.editados if r in kit.archivos)))
            lineas.append("")
        lineas.append("La configuracion completa (placas, pines, ajustes) esta en "
                      "`configuracion.json`; ktool la lee de vuelta desde el proyecto.")
        kit.archivos["LEEME.md"] = kit.archivos.get("LEEME.md", "") + "\n".join(lineas) + "\n"
        datos = self.a_dict()
        datos.pop("editados")      # el texto ya esta en sus archivos
        kit.archivos["configuracion.json"] = json.dumps(datos, indent=2, ensure_ascii=False) + "\n"

    def _pines_validos(self):
        """Solo las placas que existen y que tienen algo asignado."""
        return {p: m for p, m in self.pines.items() if p in placas.PLACAS_CON_PINES and m}

    def resumen_ajustes(self, secuencial=False):
        """[(titulo de la placa, [(ajuste, valor)])] de las placas elegidas que tienen
        ajustes: la tabla de configuracion del documento. `secuencial` incluye los
        que solo usan las maquinas de estado."""
        filas = []
        for placa in self.elegidas:
            renglones = hw_ajustes.resumen(placa, self.ajustes.get(placa), secuencial)
            if renglones:
                filas.append((hw_kit.TITULO_PLATAFORMA[placa], renglones))
        return filas

    # ------------------------------------------------------ el proyecto
    def a_dict(self):
        return {"elegidas": list(self.elegidas), "pines": self.pines,
                "ajustes": self.ajustes, "editados": self.editados, "carpeta": self.carpeta}

    @classmethod
    def desde_dict(cls, fuente):
        """Lo contrario de a_dict. Acepta el formato de antes (Fase 1), que solo
        tenia la carpeta y los pines escritos como texto por placa."""
        c = cls()
        fuente = fuente or {}
        if fuente.get("carpeta"):
            c.carpeta = fuente["carpeta"]
        validas = {clave for clave, _t in hw_kit.PLATAFORMAS}
        if "elegidas" in fuente:
            c.elegidas = [p for p in fuente["elegidas"] if p in validas]
        c.ajustes = {p: dict(v) for p, v in (fuente.get("ajustes") or {}).items()
                     if p in placas.PLACAS_CON_PINES}
        c.editados = dict(fuente.get("editados") or {})
        for placa, pines in (fuente.get("pines") or {}).items():
            if placa not in placas.PLACAS_CON_PINES:
                continue
            if isinstance(pines, str):        # formato viejo: "26, 28, 33"
                from .modelo import leer_pines
                try:
                    pines = leer_pines(pines, placas.PLACAS_CON_PINES[placa])
                except ValueError:
                    continue
            c.pines[placa] = pines
        return c
