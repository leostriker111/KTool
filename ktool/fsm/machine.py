"""Modelo de una maquina de estados sincrona (Moore / Mealy).

Una maquina son varios estados con un codigo binario asignado a unas variables
de estado Q (flip-flops) y transiciones que, segun las entradas, dicen el estado
siguiente. De aqui salen tablas de verdad sobre (Q..., entradas) que el motor de
minimizacion ya existente resuelve sin cambios.
"""

from __future__ import annotations

from . import flipflops


def _digits(name, fallback):
    d = "".join(c for c in str(name) if c.isdigit())
    return d or str(fallback)


class State:
    def __init__(self, name, code, out=None, label=None):
        self.name = str(name)
        self.code = str(code)
        self.out = None if out is None else str(out)
        self.label = str(label) if label else self.name


class Transition:
    def __init__(self, src, inp, dst, out=None):
        self.src = str(src)
        self.inp = str(inp)
        self.dst = str(dst)
        self.out = None if out is None else str(out)


class Machine:
    def __init__(self, name, inputs, state_bits, outputs=None, kind="moore"):
        self.name = name
        self.inputs = list(inputs)
        self.state_bits = list(state_bits)
        self.outputs = list(outputs or [])
        self.kind = str(kind).lower()
        self.states = []
        self.transitions = []
        self._by_name = {}
        self._by_code = {}

    # -- construccion --
    def add_state(self, name, code, out=None, label=None):
        st = State(name, code, out, label)
        if len(st.code) != len(self.state_bits):
            raise ValueError(
                f"estado {st.name!r}: codigo {st.code!r} no cabe en "
                f"{len(self.state_bits)} bits de estado"
            )
        if st.out is not None and len(st.out) != len(self.outputs):
            raise ValueError(
                f"estado {st.name!r}: salida {st.out!r} no tiene "
                f"{len(self.outputs)} bits"
            )
        self.states.append(st)
        self._by_name[st.name] = st
        self._by_code[st.code] = st
        return st

    def add_transition(self, src, inp, dst, out=None):
        if len(str(inp)) != len(self.inputs):
            raise ValueError(
                f"transicion {src}->{dst}: entrada {inp!r} no tiene "
                f"{len(self.inputs)} bits"
            )
        self.transitions.append(Transition(src, inp, dst, out))

    @classmethod
    def from_dict(cls, d):
        m = cls(
            name=d.get("name", "Maquina"),
            inputs=d.get("inputs", []),
            state_bits=d["state_bits"],
            outputs=d.get("outputs", []),
            kind=d.get("kind", "moore"),
        )
        for s in d.get("states", []):
            m.add_state(s["name"], s["code"], s.get("out"), s.get("label"))
        for t in d.get("transitions", []):
            m.add_transition(t["from"], t["in"], t["to"], t.get("out"))
        return m

    @classmethod
    def load(cls, path):
        import json
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    # -- consultas --
    def input_combos(self):
        nin = len(self.inputs)
        return [format(i, f"0{nin}b") if nin else "" for i in range(1 << nin)]

    def io_variables(self):
        return self.state_bits + self.inputs

    def next_state(self, src_name, inp):
        for t in self.transitions:
            if t.src == src_name and t.inp == inp:
                return t
        return None

    def _suffix(self, k):
        return _digits(self.state_bits[k], len(self.state_bits) - 1 - k)

    # -- tabla de estados (simbolica) --
    def state_table(self):
        rows = []
        for st in self.states:
            for inp in self.input_combos():
                t = self.next_state(st.name, inp)
                dst = self._by_name.get(t.dst) if t else None
                out = None
                if self.kind == "mealy":
                    out = t.out if t else None
                else:
                    out = st.out
                rows.append({
                    "state": st, "inp": inp,
                    "next": dst, "out": out,
                })
        return rows

    # -- columnas binarias sobre (Q..., entradas) --
    def _io_rows(self):
        nsb = len(self.state_bits)
        nin = len(self.inputs)
        nv = nsb + nin
        for i in range(1 << nv):
            b = format(i, f"0{nv}b") if nv else ""
            sbits, ibits = b[:nsb], b[nsb:]
            st = self._by_code.get(sbits)
            t = self.next_state(st.name, ibits) if st else None
            dst = self._by_name.get(t.dst) if t else None
            yield sbits, ibits, st, dst

    def nextstate_columns(self):
        cols = {f"{self.state_bits[k]}+": [] for k in range(len(self.state_bits))}
        for sbits, ibits, st, dst in self._io_rows():
            for k, b in enumerate(self.state_bits):
                v = "x" if dst is None else int(dst.code[k])
                cols[f"{b}+"].append(v)
        return cols

    def excitation_columns(self, ff_kind):
        kind = flipflops.normalize(ff_kind)
        letters = flipflops.inputs(kind)
        names = [f"{ltr}{self._suffix(k)}"
                 for k in range(len(self.state_bits)) for ltr in letters]
        cols = {nm: [] for nm in names}
        for sbits, ibits, st, dst in self._io_rows():
            for k in range(len(self.state_bits)):
                if dst is None:
                    vals = ["x"] * len(letters)
                else:
                    vals = flipflops.excite(kind, int(sbits[k]), int(dst.code[k]))
                for ltr, v in zip(letters, vals):
                    cols[f"{ltr}{self._suffix(k)}"].append(v)
        return cols

    # -- columnas de salida --
    def output_variables(self):
        return self.state_bits if self.kind == "moore" else self.io_variables()

    def output_columns(self):
        if not self.outputs:
            return {}
        if self.kind == "moore":
            nsb = len(self.state_bits)
            cols = {o: [] for o in self.outputs}
            for i in range(1 << nsb):
                code = format(i, f"0{nsb}b") if nsb else ""
                st = self._by_code.get(code)
                for j, o in enumerate(self.outputs):
                    v = "x" if (st is None or st.out is None) else int(st.out[j])
                    cols[o].append(v)
            return cols
        cols = {o: [] for o in self.outputs}
        for sbits, ibits, st, dst in self._io_rows():
            t = self.next_state(st.name, ibits) if st else None
            out = t.out if t else None
            for j, o in enumerate(self.outputs):
                v = "x" if out is None else int(out[j])
                cols[o].append(v)
        return cols
