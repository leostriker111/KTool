"""Parser descendente recursivo."""

from __future__ import annotations

from .lexer import tokenize, Token


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.pos = 0

    def peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def eat(self):
        if self.pos >= len(self.toks):
            raise ValueError("expresion mal formada: se termina antes de tiempo")
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def parse(self):
        node = self.parse_or()
        if self.peek() is not None:
            raise ValueError("expresion mal formada")
        return node

    def parse_or(self):
        node = self.parse_xor()
        while self.peek() and self.peek().kind == "OR":
            self.eat()
            node = ("or", node, self.parse_xor())
        return node

    def parse_xor(self):
        node = self.parse_and()
        while self.peek() and self.peek().kind == "XOR":
            self.eat()
            node = ("xor", node, self.parse_and())
        return node

    def _starts_operand(self, t):
        return t is not None and t.kind in ("VAR", "CONST", "NOT", "LP")

    def parse_and(self):
        node = self.parse_not()
        while True:
            t = self.peek()
            if t is None:
                break
            if t.kind == "AND":
                self.eat()
                node = ("and", node, self.parse_not())
            elif self._starts_operand(t):  # concatenacion implicita
                node = ("and", node, self.parse_not())
            else:
                break
        return node

    def parse_not(self):
        t = self.peek()
        if t and t.kind == "NOT":
            self.eat()
            return ("not", self.parse_not())
        return self.parse_postfix()

    def parse_postfix(self):
        node = self.parse_atom()
        while self.peek() and self.peek().kind == "POST":
            self.eat()
            node = ("not", node)
        return node

    def parse_atom(self):
        t = self.eat()
        if t is None:
            raise ValueError("se esperaba un operando")
        if t.kind == "VAR":
            return ("var", t.val)
        if t.kind == "CONST":
            return ("const", t.val)
        if t.kind == "LP":
            node = self.parse_or()
            close = self.eat()
            if close is None or close.kind != "RP":
                raise ValueError("falta ')'")
            return node
        raise ValueError(f"operando inesperado: {t}")


def parse(text, letras_sueltas=False):
    """letras_sueltas: cada letra es una variable (tabla de verdad). Ver lexer."""
    return Parser(tokenize(text, letras_sueltas)).parse()
