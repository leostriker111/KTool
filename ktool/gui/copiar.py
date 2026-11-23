"""El boton de copiar: solo el icono de dos cuadritos, igual en toda la ventana.

Se dibuja en un Canvas (dos rectangulos encimados) en vez de una imagen, para
no cargar archivos y para que se vea nitido con cualquier escala de Windows.
Al copiar, el icono se pone verde un momento: esa es toda la confirmacion, sin
ventanas que haya que cerrar.
"""

from __future__ import annotations

import tkinter as tk

TAMANO = 18
TRAZO = "#555"
HECHO = "#2a8a3a"


def boton_copiar(padre, obtener_texto, titulo="Copiar"):
    """Un Canvas de 18x18 que copia `obtener_texto()` al portapapeles al darle clic.

    `titulo` es lo que dice la barra de estado de quien lo use (se guarda en
    el atributo `titulo` del canvas, por si se quiere mostrar al pasar el mouse).
    """
    fondo = padre.winfo_toplevel().cget("background")
    c = tk.Canvas(padre, width=TAMANO, height=TAMANO, highlightthickness=0, bd=0,
                  cursor="hand2", background=fondo)
    # el cuadro de atras y el de enfrente, desplazados 4 px
    c.create_rectangle(2, 2, 12, 12, outline=TRAZO, width=1.4, tags="trazo")
    c.create_rectangle(6, 6, 16, 16, outline=TRAZO, width=1.4, fill=fondo, tags="trazo")
    c.titulo = titulo

    def copiar(_evento=None):
        texto = obtener_texto()
        c.clipboard_clear()
        c.clipboard_append(texto)
        c.itemconfig("trazo", outline=HECHO)
        c.after(700, lambda: c.itemconfig("trazo", outline=TRAZO))

    def encima(si):
        c.itemconfig("trazo", width=2.0 if si else 1.4)

    c.bind("<Button-1>", copiar)
    c.bind("<Enter>", lambda _e: encima(True))
    c.bind("<Leave>", lambda _e: encima(False))
    return c

