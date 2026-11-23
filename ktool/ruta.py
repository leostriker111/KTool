"""`python -m ktool --agregar-al-path`: deja el comando `ktool` en el PATH (Windows).

Para quien instalo con pip y luego `ktool` "no se reconoce": pip pone ktool.exe
en la carpeta de scripts de su Python, y esa carpeta no siempre esta en el PATH
(el Python de la Microsoft Store, o pip instalando "de usuario" porque no hay
permiso de administrador). `python -m ktool` siempre funciona, porque no
depende del PATH; desde ahi se arregla lo demas.

Tres cuidados, los mismos del instalador de Windows (packaging/setup.iss):
  - el PATH se lee CRUDO del registro: las entradas como %USERPROFILE%\...
    se quedan como variables y el valor sigue siendo REG_EXPAND_SZ;
  - se compara entrada por entrada, para no agregar la carpeta dos veces;
  - al final se avisa a Windows (WM_SETTINGCHANGE), o las terminales que se
    abran desde el menu Inicio no ven el cambio hasta cerrar sesion.
"""

from __future__ import annotations

import sys


def carpeta_de_los_comandos():
    """Donde dejo pip ktool.exe, segun su propio registro de archivos (RECORD).

    Devuelve None si ktool no se instalo con pip (por ejemplo, con el
    instalador de Windows, o corriendo desde la carpeta del codigo).
    """
    try:
        from importlib import metadata
        archivos = metadata.files("ktool") or []
    except Exception:  # PackageNotFoundError y similares
        return None
    for f in archivos:
        if f.name.lower() in ("ktool.exe", "ktool"):
            return str(f.locate().resolve().parent)
    return None


def mismo_lugar(a, b):
    """Dos entradas del PATH son la misma carpeta aunque difieran en
    mayusculas o en la diagonal final."""
    return a.strip().rstrip("\\/").lower() == b.strip().rstrip("\\/").lower()


def path_con(crudo, carpeta):
    """El PATH `crudo` con `carpeta` al final, una sola vez y sin huecos (';;').

    Devuelve (nuevo, ya_estaba)."""
    entradas = [e for e in crudo.split(";") if e.strip()]
    if any(mismo_lugar(e, carpeta) for e in entradas):
        return ";".join(entradas), True
    return ";".join(entradas + [carpeta]), False


def _avisar_a_windows():
    """WM_SETTINGCHANGE a todas las ventanas: el Explorador relee el entorno."""
    import ctypes
    from ctypes import wintypes
    HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001A, 0x0002
    resultado = wintypes.DWORD()
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
        SMTO_ABORTIFHUNG, 5000, ctypes.byref(resultado))


def agregar_al_path():
    """Lo que corre la opcion de la CLI. Devuelve el codigo de salida."""
    if sys.platform != "win32":
        print("Esta opcion es para Windows. En Linux/macOS, agrega a tu PATH la "
              "carpeta que pip menciono en su aviso (suele ser ~/.local/bin).")
        return 1
    carpeta = carpeta_de_los_comandos()
    if carpeta is None:
        print("ktool no aparece instalado con pip, asi que no hay carpeta que agregar.\n"
              "Si usaste el instalador de Windows, el ya lo agrego al PATH: abre una "
              "terminal nueva.")
        return 1

    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                        winreg.KEY_READ | winreg.KEY_WRITE) as clave:
        try:
            crudo, _tipo = winreg.QueryValueEx(clave, "Path")  # sin expandir
        except FileNotFoundError:
            crudo = ""
        nuevo, ya_estaba = path_con(crudo, carpeta)
        if ya_estaba:
            print(f"La carpeta ya estaba en tu PATH: {carpeta}\n"
                  "Si `ktool` no se reconoce, cierra la terminal y abre una nueva.")
            return 0
        winreg.SetValueEx(clave, "Path", 0, winreg.REG_EXPAND_SZ, nuevo)
    _avisar_a_windows()
    print(f"Listo: agregue {carpeta} a tu PATH.\n"
          "Abre una terminal NUEVA y escribe:  ktool -h")
    return 0
