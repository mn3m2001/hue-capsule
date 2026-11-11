"""SymPy verification kit: one source for the check AND the typeset solution. Course-agnostic.

Use it from the per-course `_verify/verify.py`:

    import sys; sys.path.insert(0, r"<skill>/scripts")
    from verify_kit import Kit, symbols, Eq
    K = Kit(course_dir)
    p = K.problem("PROB-S1-03")
    Q, k, A, L, dT = symbols("Q k A L DeltaT")
    p.calc(A, pi * D**2 / 4, {D: 0.20}, unit=r"\\text{m}^2")            # computes, remembers A, writes the LaTeX line
    p.calc(dT, Q * L / (k * A), {Q: 800, L: 0.004, k: 237}, unit=r"^\\circ\\text{C}")   # uses the remembered A
    p.expect(dT, 0.43, rel_tol=0.01, source="Sheet1_Model_Answers")      # compares with the published answer
    K.save()                                                             # _verify/results.json + _verify/steps.json
    # then: python verify_kit.py <course_dir> --merge   (fills `solution_tex` in the ledger from steps.json)

Every `calc` line becomes `lhs = symbolic formula = formula with numbers = value unit` in LaTeX, so the verified number and the
printed equation can never disagree. Bessel-function steps (circular fins) are not symbolic: use `p.note_tex(...)` and `p.expect(...)`.
"""
import json
import os
import sys

import sympy as sp
from sympy import Eq, UnevaluatedExpr, symbols, pi  # noqa: F401  (re-exported for the course scripts)


def _fmt(v, digits=4):
    return sp.latex(sp.N(v, digits))


class Problem:
    def __init__(self, kit, pid):
        self.kit, self.pid = kit, pid
        self.vals = {}
        self.tex = []

    def calc(self, lhs, rhs, values=None, unit="", note=None):
        """Evaluate rhs with `values` plus everything computed before; store lhs; append one LaTeX line."""
        rhs = sp.sympify(rhs)  # plain numbers are allowed
        vals = dict(self.vals)
        vals.update(values or {})
        self.vals.update(values or {})
        num = sp.N(rhs.subs(vals))
        shown = rhs.xreplace({s: sp.Symbol(sp.latex(sp.N(v, 4))) for s, v in vals.items() if s in rhs.free_symbols})
        self.vals[lhs] = num
        line = "%s=%s=%s=%s" % (sp.latex(lhs), sp.latex(rhs), sp.latex(shown, mul_symbol="times"), _fmt(num))
        if unit:
            line += r"\,%s" % unit
        self.tex.append(line)
        return float(num)

    def note_tex(self, line):
        """A step that is not symbolic (chart reading, Bessel function): keep the LaTeX by hand."""
        self.tex.append(line)

    def expect(self, symbol_or_value, published, rel_tol=0.01, source="", desc="", suffix=""):
        v = self.vals[symbol_or_value] if symbol_or_value in self.vals else symbol_or_value
        v = float(sp.N(v))
        ok = abs(v - published) <= rel_tol * abs(published)
        self.kit.checks.append({"id": self.pid + ("/" + suffix if suffix else ""), "ok": bool(ok), "desc": desc or str(symbol_or_value),
                                "computed": round(v, 5), "published": published, "rel_tol": rel_tol, "published_in": source})
        return ok


class Kit:
    def __init__(self, course):
        self.course = course
        self.checks, self.problems = [], {}

    def problem(self, pid):
        self.problems[pid] = Problem(self, pid)
        return self.problems[pid]

    def save(self):
        d = os.path.join(self.course, "_verify")
        os.makedirs(d, exist_ok=True)
        rp, sp_ = os.path.join(d, "results.json"), os.path.join(d, "steps.json")
        try:
            with open(rp, encoding="utf-8") as f:
                other = json.load(f).get("tool") != "sympy (verify_kit)"
        except (OSError, ValueError):
            other = False
        if other:  # an existing results.json from another verifier is never overwritten
            rp, sp_ = os.path.join(d, "sympy_results.json"), os.path.join(d, "sympy_steps.json")
            print("NOTE: _verify/results.json belongs to another verifier; writing sympy_results.json and sympy_steps.json instead")
        with open(rp, "w", encoding="utf-8") as f:
            json.dump({"tool": "sympy (verify_kit)", "checks": self.checks}, f, ensure_ascii=False, indent=1)
        with open(sp_, "w", encoding="utf-8") as f:
            json.dump({k: p.tex for k, p in self.problems.items()}, f, ensure_ascii=False, indent=1)
        bad = [c for c in self.checks if not c["ok"]]
        print("%d of %d checks ok" % (len(self.checks) - len(bad), len(self.checks)))
        for c in bad:
            print("FAIL", c)
        return not bad


def merge(course):
    """Fill `solution_tex` of ledger problems that have none from _verify/steps.json (never overwrites hand-written ones)."""
    lp = os.path.join(course, "course_curriculum_ledger.json")
    with open(lp, encoding="utf-8") as f:
        ledger = json.load(f)
    sp_ = os.path.join(course, "_verify", "steps.json")
    if not os.path.isfile(sp_):
        sp_ = os.path.join(course, "_verify", "sympy_steps.json")
    with open(sp_, encoding="utf-8") as f:
        steps = json.load(f)
    n = 0
    for m in ledger.get("modules", []):
        for p in m.get("problems", []):
            if not p.get("solution_tex") and steps.get(p["id"]):
                p["solution_tex"] = steps[p["id"]]
                n += 1
    with open(lp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=1)
    print("merged solution_tex into %d problem(s)" % n)
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[2] == "--merge":
        sys.exit(merge(sys.argv[1]))
    print("usage: verify_kit.py <course_dir> --merge   (the kit itself is imported by _verify/verify.py)")
    sys.exit(2)
