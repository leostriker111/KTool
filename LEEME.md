<p align="center">
  <a href="README.md">English</a> · <b>Español</b>
</p>

<div align="center">

<img src="recursos/ktool.svg" width="104" alt="KTool">

# KTool

### Lógica digital, minimizada exacto — y te dice cuándo el XOR sale más barato.

Llenas una tabla de verdad (a mano, desde una expresión o desde una lista de
minterminos) y te devuelve el mapa de Karnaugh, las ecuaciones mínimas en SOP
**y** POS, el diagrama de compuertas, y un documento HTML con todo junto.

[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-2c7a51?style=flat-square)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Pruebas](https://img.shields.io/github/actions/workflow/status/leostriker111/KTool/ci.yml?branch=main&style=flat-square&label=pruebas)](../../actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/leostriker111/KTool?style=flat-square&label=descargar)](../../releases/latest)
![Sin dependencias](https://img.shields.io/badge/dependencias-ninguna-0e9f6e?style=flat-square)

<br>

<img src="docs/imagenes/reporte-kmap.png" width="880" alt="Parte de un reporte generado: ecuaciones SOP, POS y XOR con su costo, y los dos mapas de Karnaugh con los grupos circulados en colores">

</div>

---

Esa imagen es un reporte de verdad, no una maqueta — y enseña justo lo que esta
herramienta hace y un K-map a mano no. Para esa función, el SOP cuesta 3
compuertas y el POS cuesta 3, pero la función es la paridad de B y D, así que
**`(B ^ D)'` cuesta 2**. KTool revisa ese tercer camino siempre y te avisa cuando
gana.

## Qué es

Una herramienta con **dos caras**: una **interfaz por línea de comandos** para
cuando ya tienes los minterminos y quieres la respuesta en la terminal, y una
**interfaz gráfica** que se porta como una hoja de cálculo para cuando estás
llenando la tabla a mano. Las dos producen el mismo documento HTML autocontenido.

Se escribió para la materia de sistemas digitales, y se le nota: trabaja con
varias salidas a la vez, cuenta el costo de lo que propone, y señala los términos
que dos salidas podrían compartir, porque eso es lo que de verdad pregunta una
tarea.

## Propósito y alcance

**El propósito.** Estar en lo correcto, y enseñar el procedimiento. Minimizar a
ojo sobre un mapa de Karnaugh es donde se pierden los puntos — un grupo que no
viste, un *don't care* desperdiciado, un POS que habría salido más barato. Esto
hace la parte mecánica exacta, y luego te entrega un documento que puedes leer y
revisar.

**Qué abarca.** Hasta **6 variables** y **10 salidas** en la misma tabla.
Minimización Quine-McCluskey con *don't cares*, SOP y POS lado a lado con su
costo, XOR/XNOR como tercer candidato, detección de términos compartidos entre
salidas, mapas de Karnaugh a color, diagramas de compuertas, y exportación a
siete lenguajes.

**Qué no es.** Un proyecto de práctica, no una herramienta de diseño
profesional. Las cuentas son exactas —tabla de verdad más Quine-McCluskey— pero
confirma la salida antes de construir algo encima.

## Contenido

- [Qué es](#qué-es) · [Propósito y alcance](#propósito-y-alcance)
- [Instalación](#instalación)
- [Cómo se empieza (CLI)](#cómo-se-empieza-cli) · [Sintaxis de expresiones](#sintaxis-de-expresiones)
- [Cómo se usa (GUI)](#cómo-se-usa-gui)
- [Qué sale](#qué-sale) · [Limitaciones conocidas](#limitaciones-conocidas)
- [Para quien quiera meter mano](#contribuir)

> **El comando se llama `ktool`.** `kmap` es un alias histórico —el proyecto nació
> haciendo sólo mapas de Karnaugh— y sigue funcionando igual.

## Instalación

**A — Instalador de Windows (lo más fácil).** Baja el más reciente de
[Releases](../../releases/latest) y córrelo; deja `ktool` en el `PATH`. O en una
línea de PowerShell:

```powershell
irm https://raw.githubusercontent.com/leostriker111/KTool/main/get-ktool.ps1 | iex
```

**B — pip**, si ya tienes Python:

```powershell
pip install git+https://github.com/leostriker111/KTool.git
```

**C — desde el código:**

```powershell
git clone https://github.com/leostriker111/KTool.git
cd KTool
packaging\install.ps1
```

Sin instalar nada, desde la carpeta del proyecto: `python -m ktool ...`

## Cómo se empieza (CLI)

```powershell
ktool -e "A'B + C" --open                 # armar la tabla desde una expresion
ktool -n 3 -m 1,4,5,6 -d 2,7              # minterminos y don't cares
ktool -n 4 -m 0x1,0b11,5 --text           # mezcla de bases, ecuaciones en consola
ktool -n 3 --truth 01x011x1 --form both   # vector de salida directo
ktool ... --gates-only                    # solo compuertas, sin K-map ni tabla
ktool gui                                 # abrir la ventana
ktool -h                                  # ayuda completa
```

| switch | para qué sirve |
|---|---|
| `-n, --vars N` | Número de variables (2 a 6). |
| `-e, --expr "..."` | Expresión booleana; arma la tabla evaluando todos los casos. |
| `-m, --minterms ...` | Minterminos en decimal, `0x` hex o `0b` binario. |
| `-d, --dontcares ...` | *Don't cares*, misma sintaxis. |
| `--truth 01x10...` | Vector de salida directo (largo `2^n`, admite `x`). |
| `--name Y` | Nombre de la salida. |
| `--form sop\|pos\|auto\|both` | Qué forma mostrar. `auto` elige la más barata. |
| `--no-kmap` / `--no-circuit` / `--no-table` | Dejar fuera una sección. |
| `--gates-only` | Sólo compuertas (apaga K-map y tabla). |
| `--text` | Sólo imprime las ecuaciones en la terminal. |
| `--out archivo.html` / `--open` / `--title "..."` | Dónde va el documento, si se abre, y su título. |

### Sintaxis de expresiones

| operación | cómo se escribe |
|---|---|
| AND | `ab`, `a*b`, `a.b`, `a&b` |
| OR | `a+b`, `a\|b` |
| NOT | `a'`, `!a`, `~a` |
| XOR | `a^b` |
| XNOR | `(a^b)'` |

Las variables son las letras `A` a `F`. Precedencia: NOT, luego AND, luego XOR,
luego OR.

## Cómo se usa (GUI)

```powershell
ktool gui
```

Una tabla al estilo de los solucionadores clásicos. Arriba eliges el número de
variables y de salidas, activas la columna de notas, y escoges la forma (SOP,
POS, auto o ambas). La barra de expresión llena una columna entera evaluando lo
que escribas. *Ecuaciones* muestra el resultado en el panel de abajo y *Generar
documento* arma el HTML.

Llenar la tabla rápido es la parte que de verdad se diseñó:

| acción | cómo |
|---|---|
| Seleccionar un rango | Arrastra sobre las celdas, o <kbd>Shift</kbd>+clic para extender. Se marcan en azul. |
| Poner toda la selección | <kbd>1</kbd>, <kbd>0</kbd> o <kbd>x</kbd> cambia todas las celdas elegidas de un golpe. |
| Ciclar una celda | Doble clic: `0 → 1 → x`. |
| Copiar y pegar | <kbd>Ctrl</kbd>+<kbd>C</kbd>/<kbd>V</kbd>/<kbd>X</kbd>, en formato que Excel entiende. |
| Renombrar una salida | Clic en su encabezado. |

El menú *Ayuda* trae la guía rápida, la lista de atajos y el enlace al
repositorio.

## Qué sale

Un documento HTML autocontenido. Por cada salida: las ecuaciones SOP y POS con
su costo, la forma recomendada, el mapa de Karnaugh con los grupos circulados en
colores y nombrados en una leyenda, el circuito, y la tabla de verdad.

Con más de una salida agrega una sección con los términos que aparecen en varias
—las compuertas que físicamente podrías compartir— y un circuito combinado.

Las ecuaciones salen además en **Verilog, VHDL, ABEL, Logisim, C, Python y
LaTeX**, cada una con su botón de copiar.

## Limitaciones conocidas

Vale la pena decirlas claro, porque todo el chiste es ser confiable:

- **La detección de XOR/XNOR** aplica cuando la función completa es la paridad de
  un subconjunto de las variables. No factoriza XOR parciales dentro de un SOP
  grande.
- **El circuito da por hecho que hay literales complementados** disponibles
  (rieles `A'`), y no dibuja un esquemático único con las compuertas compartidas
  ya integradas — ésas se listan aparte.
- **No hay álgebra de Boole simbólica** sobre expresiones arbitrarias.

<br>

---

<div align="center">

## 🔧 Para quien quiera meter mano

*Todo lo de arriba es lo que hace. Todo lo de abajo es cómo lo hace.*

</div>

---

### Contribuir

La rama `main` está protegida, así que los cambios entran por Pull Request. Mira
[CONTRIBUTING.md](CONTRIBUTING.md).

Donde más rendiría la ayuda:

- **Factorización de XOR parciales** — la limitación real más grande de arriba, y
  la que más cambiaría la calidad de las respuestas.
- **Un esquemático combinado único** con las compuertas compartidas dibujadas de
  verdad, en vez de listadas.
- **Más lenguajes de salida** en `codegen.py` — SystemVerilog y VHDL-2008 son los
  huecos obvios.
- **Verificación contra un minimizador conocido** (Espresso) sobre funciones al
  azar, como prueba.

Las notas de diseño están en [docs/DESIGN.md](docs/DESIGN.md).

### De qué está hecho

**Python 3.8+ sin una sola dependencia externa** — puro librería estándar, y
Tkinter para la ventana. Es una restricción a propósito: esto se corre en
computadoras de laboratorio donde no puedes instalar nada, y un `pip install` ya
sería un obstáculo de más. Es también la razón de que la salida sea un solo
archivo HTML y no un PDF renderizado.

### Los módulos

Unas 2,400 líneas, repartidas por trabajo.

<details open>
<summary><b>core — las matemáticas</b></summary>

<br>

| módulo | líneas | qué hace |
|---|--:|---|
| `core/lexer.py` | 44 | Convierte una expresión en tokens. |
| `core/parser.py` | 75 | De tokens a árbol sintáctico, con la precedencia de arriba. |
| `core/ast.py` | 52 | Los nodos del árbol, y evaluar uno para una entrada dada. |
| `core/table.py` | 74 | La tabla de verdad: minterminos, *don't cares*, varias salidas. |
| `core/qm.py` | 108 | **Quine-McCluskey.** Implicantes primos y la cobertura — la parte exacta. |
| `core/simplify.py` | 151 | Corre los tres candidatos (SOP, POS, XOR), los cotiza en compuertas y literales, y elige. |
| `core/kmap_layout.py` | 46 | El orden en código Gray, para que las celdas contiguas de verdad lo sean. |

</details>

<details>
<summary><b>render — el documento</b></summary>

<br>

| módulo | líneas | qué hace |
|---|--:|---|
| `render/report.py` | 318 | Arma el HTML: todo en línea, sin archivos externos. |
| `render/circuit.py` | 374 | Dibuja las compuertas. El archivo más grande, porque acomodar un esquemático es de verdad más difícil que minimizarlo. |
| `render/codegen.py` | 170 | Los siete lenguajes de salida. |
| `render/kmap.py` | 112 | El mapa, con cada grupo circulado en su color. |

</details>

<details>
<summary><b>gui y cli</b></summary>

<br>

| módulo | líneas | qué hace |
|---|--:|---|
| `gui/app.py` | 680 | La ventana y la tabla tipo hoja de cálculo. |
| `gui/displays.py` | 89 | Mostrar los resultados en el panel de abajo. |
| `cli.py` | 134 | Los argumentos y la tubería. |
| `theme.py` | 23 | Los colores que comparten la ventana y el reporte. |

</details>

### La decisión detrás de lo interesante

Casi todas las herramientas de K-map te dan SOP. Algunas te dan SOP y POS. La
razón de que ésta calcule un **tercer** candidato es que para toda una familia de
funciones comunes —paridad, comparadores, sumadores— las dos primeras son
respuestas equivocadas a la pregunta «qué sale más barato». Una función de
paridad de 4 variables son cuatro AND y un OR en SOP, y un solo XNOR en la
realidad.

Así que `simplify.py` no minimiza, **compite**: construye los tres, los cotiza en
compuertas y literales, y reporta al ganador junto con los dos perdedores para que
veas por cuánto. Ésa es también la razón de que el costo salga impreso junto a
cada ecuación y no sólo junto a la elegida.

### Licencia

[MIT](LICENSE).

### Proyectos relacionados

- **[Logisim Evolution](https://github.com/logisim-evolution/logisim-evolution)** —
  *ése para simular el circuito;* KTool exporta directo a su formato.
- **[Espresso](https://es.wikipedia.org/wiki/Espresso_(minimizador_l%C3%B3gico))** —
  *ése de 6 variables en adelante,* donde la minimización exacta deja de ser
  práctica y toman el relevo las heurísticas.
