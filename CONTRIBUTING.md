# Contribuir a ktool

Gracias por el interés. Las sugerencias, reportes de errores y mejoras son
bienvenidos.

## Cómo proponer algo

- Para una idea o un error, abre un [issue](https://github.com/leostriker111/ktool/issues).
  Si es un error, incluye qué entrada usaste (expresión, minterminos o vector) y
  qué resultado esperabas.
- Para un cambio de código, manda un *pull request*. La rama `main` está protegida,
  así que todo entra revisado por PR; no se hace push directo.

## Trabajar con el código

No hay dependencias externas; basta Python 3.8 o más nuevo.

```powershell
git clone https://github.com/leostriker111/ktool.git
cd ktool
python -m ktool -n 3 -m 1,4,5,6 -d 2,7 --text
python -m ktool gui
```

Antes de mandar un PR, corre las mismas verificaciones que la integración continua:

```powershell
python -m unittest discover -s tests -v
python -c "import ktool"
python -m ktool -e "A^B^C" --text
python -m ktool -n 4 -m 0,1,2,3,8,9 --out salida.html
```

Las pruebas usan `unittest` de la biblioteca estándar: no hay nada que instalar.
Si arreglas un error, agrega antes la prueba que lo reproduce.

## Estilo

- Python puro, sin agregar dependencias salvo que sea indispensable.
- Nombres y mensajes en español, como el resto del proyecto.
- Cambios enfocados: un PR, una cosa.

La estructura interna y los algoritmos están explicados en [DESIGN.md](docs/DESIGN.md).
