"""Tokenizador (scanner).

Dos modos, porque el proyecto lee expresiones de dos mundos distintos:

- `letras_sueltas=False` (por omision): un identificador es una corrida de
  alfanumericos, como en cualquier lenguaje. Es lo que necesita traducir una
  expresion libre a Verilog/VHDL, donde `clk` y `enable` son un solo nombre.

- `letras_sueltas=True`: cada letra es una variable. Es lo que necesita una
  tabla de verdad, donde las variables son A..F y pegar dos letras significa
  AND (`AB` = A AND B), igual que se escribe un mintermino a mano.
"""

from __future__ import annotations


class Token:
    def __init__(self, kind, val=None):
        self.kind = kind
        self.val = val

    def __repr__(self):
        return f"{self.kind}:{self.val}" if self.val else self.kind


_SYMBOLS = {
    '+': "OR", '|': "OR",
    '*': "AND", '.': "AND", '&': "AND",
    '^': "XOR",
    '!': "NOT", '~': "NOT",
    "'": "POST",
    '(': "LP",
    ')': "RP"
}


def tokenize(text, letras_sueltas=False):
    toks = []
    i = 0
    s = text
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c.isalpha() or (c == "_" and not letras_sueltas):
            if letras_sueltas:
                # cada letra es su propia variable; el parser junta los
                # VAR seguidos con un AND implicito
                toks.append(Token("VAR", c))
                i += 1
                continue
            j = i
            while j < len(s) and (s[j].isalnum() or s[j] == "_"):
                j += 1
            toks.append(Token("VAR", s[i:j]))
            i = j
            continue
        if c in "01":
            toks.append(Token("CONST", int(c)))
            i += 1
            continue
        if c in _SYMBOLS:
            toks.append(Token(_SYMBOLS[c]))
            i += 1
            continue
        raise ValueError(f"caracter invalido en expresion: {c!r}")
    return toks
