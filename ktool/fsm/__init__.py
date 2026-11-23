"""Maquinas de estado sincronas: modelo, flip-flops y excitacion.

Reutiliza el motor de minimizacion de `core`: una maquina son varias tablas de
verdad (una por entrada de flip-flop y por salida).
"""

from __future__ import annotations

from .machine import Machine, State, Transition
from . import flipflops

__all__ = ["Machine", "State", "Transition", "flipflops"]
