"""El molde del encapsulado: uno solo, ajustable, para cualquier numero de pines.

No hay un dibujo por chip. Hay **un molde** que se calcula: le das los pines y
saca el tamano, las columnas de protoboard que ocupa y el SVG. Un DIP de 4, de
14, de 20 o de 40 salen del mismo codigo, porque un DIP siempre es lo mismo:
dos hileras de pines a 0.1 pulgadas, separadas 0.3 (o 0.6 si es ancho), con la
muesca arriba y el pin 1 a su izquierda.

Medidas reales (JEDEC): paso de 2.54 mm entre pines, 7.62 mm entre hileras hasta
20 pines y 15.24 mm de 22 en adelante. De ahi sale todo lo demas.
"""

from __future__ import annotations

PASO_MM = 2.54          # entre pines contiguos de la misma hilera
ANGOSTO_MM = 7.62       # entre hileras, encapsulado de 0.3"
ANCHO_MM = 15.24        # entre hileras, encapsulado de 0.6"


def geometria(pines):
    """Las medidas del encapsulado, calculadas. Nada escrito a mano."""
    if pines < 4 or pines % 2:
        raise ValueError(f"un DIP tiene un numero par de pines, al menos 4 (pediste {pines})")
    por_hilera = pines // 2
    return {
        "pines": pines,
        "por_hilera": por_hilera,
        "columnas": por_hilera,                      # columnas de protoboard que ocupa
        "paso_mm": PASO_MM,
        "entre_hileras_mm": ANGOSTO_MM if pines <= 20 else ANCHO_MM,
        "largo_mm": round(por_hilera * PASO_MM + 1.4, 2),
    }


def lado(pin, pines):
    """'izq' o 'der'. El pin 1 arriba a la izquierda, y se numera en herradura."""
    if not 1 <= pin <= pines:
        raise ValueError(f"el pin {pin} no existe en un DIP de {pines}")
    return "izq" if pin <= pines // 2 else "der"


def fila(pin, pines):
    """Fila del pin contando desde arriba, empezando en 0."""
    por_hilera = pines // 2
    return pin - 1 if pin <= por_hilera else pines - pin


def pin_en(lado_, fila_, pines):
    """El inverso: que pin cae en ese lado y esa fila."""
    por_hilera = pines // 2
    if not 0 <= fila_ < por_hilera:
        raise ValueError(f"la fila {fila_} no existe en un DIP de {pines}")
    return fila_ + 1 if lado_ == "izq" else pines - fila_


def svg(pines, x=0, y=0, paso=22, etiquetas=None, nombre="", relieve=True):
    """Dibuja el encapsulado. `paso` es el tamano de una celda de protoboard.

    `etiquetas` es {pin: texto} y se dibuja junto a cada pata. `relieve` le pone
    el sombreado que lo levanta un poco del tablero.
    """
    g = geometria(pines)
    filas = g["por_hilera"]
    ancho_canal = paso * (g["entre_hileras_mm"] / PASO_MM)
    alto = filas * paso
    cuerpo_x = x + paso * 0.18
    cuerpo_w = ancho_canal - paso * 0.36

    partes = []
    if relieve:
        partes.append(
            f'<rect x="{cuerpo_x + 1.5:.1f}" y="{y + 2.5:.1f}" '
            f'width="{cuerpo_w:.1f}" height="{alto:.1f}" rx="2" '
            f'fill="#000" opacity="0.28"/>'
        )
    partes.append(
        f'<rect x="{cuerpo_x:.1f}" y="{y:.1f}" width="{cuerpo_w:.1f}" '
        f'height="{alto:.1f}" rx="2" fill="#2f3237" stroke="#15171a"/>'
    )
    if relieve:
        # una banda clara arriba y una oscura abajo: el plastico se ve levantado
        partes.append(
            f'<rect x="{cuerpo_x + 1:.1f}" y="{y + 1:.1f}" '
            f'width="{cuerpo_w - 2:.1f}" height="{max(2, alto * 0.10):.1f}" rx="1" '
            f'fill="#ffffff" opacity="0.16"/>'
        )
        partes.append(
            f'<rect x="{cuerpo_x + 1:.1f}" y="{y + alto - max(2, alto * 0.09):.1f}" '
            f'width="{cuerpo_w - 2:.1f}" height="{max(2, alto * 0.08):.1f}" rx="1" '
            f'fill="#000000" opacity="0.30"/>'
        )

    # la muesca de arriba, que es la que dice donde esta el pin 1
    cx = cuerpo_x + cuerpo_w / 2
    partes.append(
        f'<path d="M {cx - paso*0.26:.1f},{y} A {paso*0.26:.1f},{paso*0.26:.1f} 0 0 0 '
        f'{cx + paso*0.26:.1f},{y}" fill="#15171a"/>'
    )

    for pin in range(1, pines + 1):
        f = fila(pin, pines)
        cy = y + f * paso + paso / 2
        izquierda = lado(pin, pines) == "izq"
        px = cuerpo_x - paso * 0.18 if izquierda else cuerpo_x + cuerpo_w
        partes.append(
            f'<rect x="{px:.1f}" y="{cy - paso*0.16:.1f}" width="{paso*0.18:.1f}" '
            f'height="{paso*0.32:.1f}" fill="#c9ccd1" stroke="#8a8f96" stroke-width="0.5"/>'
        )
        partes.append(
            f'<text x="{cx:.1f}" y="{cy + 3:.1f}" font-size="{paso*0.34:.1f}" '
            f'fill="#9aa0a8" text-anchor="middle">{pin}</text>'
            if pines <= 16 else ""
        )
        if etiquetas and pin in etiquetas:
            tx = px - paso * 0.25 if izquierda else px + paso * 0.43
            anclaje = "end" if izquierda else "start"
            partes.append(
                f'<text x="{tx:.1f}" y="{cy + 3:.1f}" font-size="{paso*0.38:.1f}" '
                f'text-anchor="{anclaje}" fill="#333">{etiquetas[pin]}</text>'
            )

    if nombre:
        partes.append(
            f'<text x="{cx:.1f}" y="{y - 5:.1f}" font-size="{paso*0.46:.1f}" '
            f'text-anchor="middle" fill="#333" font-weight="bold">{nombre}</text>'
        )
    return "".join(p for p in partes if p)
