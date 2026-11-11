"""Draft ledger problems from a text PDF (a sheet, a question bank, an old exam). Writes nothing into the ledger. Usage:

    python draft_ledger.py <course_dir> <pdf name or path> [--label "Sheet 3"]

Splits the PDF into problems at markers like `[3]`, `3.` or `Q3`, and for each one drafts: id, source_file, page, source_ref
("Sheet 3 · Q3"), the first sentence as title, `crop_start` / `crop_end` (first words of this and of the next problem, used to crop
the page image), `givens_tex` (every "name = value unit" and "5-cm-thick" found, as LaTeX), and `parts` asks (one per
"Determine/Calculate/Find ..." clause or (a)/(b)/(c) item). Output: `_audit/ledger_draft.json`. Explanations, solution steps and
the answers are NOT drafted: write them with `verify_kit.py` (steps) and the Arabic/English fields. A scanned PDF (no text) is refused.
"""
import json
import os
import re
import sys

UNITS = r"(?:W/m2|W/m\^2|W/m\s*[·.]\s*°C|W/m2\s*[·.]\s*°C|W/m\s*[·.]\s*K|W|kW|kg|kJ|MHz|kHz|Hz|GHz|dB|mV|V|mA|A|cm|mm|m|s|h|min|°C|K)"
NUM = r"-?\d+(?:\.\d+)?"


def givens(text):
    out, seen = [], set()
    for m in re.finditer(r"([A-Za-z]\w{0,3}(?:_\{?\w+\}?)?)\s*=\s*(%s)\s*(%s)?" % (NUM, UNITS), text):
        name, val, unit = m.group(1), m.group(2), (m.group(3) or "")
        key = (name, val)
        if key not in seen:
            seen.add(key)
            out.append("%s=%s%s" % (name, val, (r"\,\text{" + unit.replace(" ", "") + "}") if unit else ""))
    for m in re.finditer(r"(?<![\w.])(%s)\s*(°C|W/m2\s*[·.]\s*°C|W/m\s*[·.]\s*°C|kW|W|kg|kJ|MHz|kHz|GHz|Hz|dB)(?![\w/])" % NUM, text):
        val, unit = m.group(1), re.sub(r"\s+", "", m.group(2))
        key = ("v", val, unit)
        if key not in seen and not any(g.startswith(tuple("%s=%s" % (n, val) for n in "kTh")) for g in out):
            seen.add(key)
            out.append(r"%s\,	ext{%s}" % (val, unit))
    for m in re.finditer(r"(%s)-(cm|mm|m|W|kg|s|h|min|°C)(?:-(\w+))?" % NUM, text):
        val, unit, word = m.group(1), m.group(2), m.group(3) or ""
        key = (val, unit, word)
        if key not in seen:
            seen.add(key)
            out.append(r"%s\,\text{%s}%s" % (val, unit if unit != "°C" else "°C", (r"\ \text{(%s)}" % word) if word else ""))
    return out


def asks(text):
    parts = re.split(r"\(\s*([a-d])\s*\)", text)
    found = []
    if len(parts) > 2:
        for i in range(1, len(parts) - 1, 2):
            found.append("(%s) %s" % (parts[i], re.split(r"\.\s", parts[i + 1].strip())[0][:140]))
    else:
        for m in re.finditer(r"((?:Determine|Calculate|Find|Estimate|Compute)[^.?]*[.?])", text):
            found.append(m.group(1).strip()[:160])
    return found or ["TODO: write the requirement"]


def main(argv):
    if len(argv) < 2:
        print("usage: draft_ledger.py <course_dir> <pdf name or path> [--label 'Sheet 3']")
        return 2
    course, pdf = argv[0], argv[1]
    label = argv[argv.index("--label") + 1] if "--label" in argv else os.path.splitext(os.path.basename(pdf))[0]
    import fitz
    path = pdf
    if not os.path.isfile(path):
        cfg = json.load(open(os.path.join(course, "course.json"), encoding="utf-8"))
        for dp, _, files in os.walk(cfg.get("root", course)):
            if os.path.basename(pdf) in files:
                path = os.path.join(dp, os.path.basename(pdf))
                break
    if not os.path.isfile(path):
        print("FAIL: %s not found. Fix: give the full path" % pdf)
        return 1
    doc = fitz.open(path)
    pages = [(i + 1, p.get_text()) for i, p in enumerate(doc)]
    if sum(len(t.strip()) for _, t in pages) < 100:
        print("FAIL: %s has no text layer (scanned). Fix: python scripts/ocr_sources.py, or write the ledger by hand" % pdf)
        return 1
    items = []  # (page, number, text)
    pat = re.compile(r"(?:^|\n)\s*(?:\[\s*(\d+)\s*\]|(\d+)\s*[.)]|Q\s*(\d+)\s*[.:)]?)\s+(?=[A-Z])")
    for pg, t in pages:
        ms = list(pat.finditer(t))
        for j, m in enumerate(ms):
            end = ms[j + 1].start() if j + 1 < len(ms) else len(t)
            body = re.split(r"Answer\s*:", re.sub(r"\s+", " ", t[m.end():end]).strip())[0].strip()
            num = next(g for g in m.groups() if g)
            if len(body) > 25:
                items.append((pg, num, body))
    drafts = []
    for k, (pg, num, body) in enumerate(items):
        nxt = items[k + 1] if k + 1 < len(items) and items[k + 1][0] == pg else None
        words = lambda s: " ".join(s.split()[:4])  # noqa: E731
        drafts.append({"id": "PROB-%s-%02d" % (re.sub(r"\W+", "", label).upper(), int(num)), "title": "%s Q%s: %s" % (label, num, body.split(". ")[0][:90]),
                       "source_file": os.path.basename(path), "page_or_slide": pg, "source_ref": "%s · Q%s" % (label, num),
                       "crop_start": words(body), **({"crop_end": words(nxt[2])} if nxt else {}),
                       "givens_tex": givens(body), "parts": [{"ask_en": a, "ask_ar": "TODO", "steps": [0, 0], "answer_tex": "TODO"} for a in asks(body)],
                       "explain_ar": "TODO", "explain_en": "TODO", "text": body})
    os.makedirs(os.path.join(course, "_audit"), exist_ok=True)
    with open(os.path.join(course, "_audit", "ledger_draft.json"), "w", encoding="utf-8") as f:
        json.dump(drafts, f, ensure_ascii=False, indent=1)
    print("%d problem(s) drafted from %s -> _audit/ledger_draft.json (TODO fields are yours to fill)" % (len(drafts), os.path.basename(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
