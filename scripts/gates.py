"""Gate functions for hue-capsule v4. Read-only for the agent: never edit this file inside a course run.

Every gate returns (ok: bool, messages: list[str], evidence: dict). A gate never "warns and passes":
anything missing is a failure.
"""
import glob
import json
import os
import re
import unicodedata

ATTR_OFFLINE = 0x1000
ATTR_RECALL_ON_OPEN = 0x40000
ATTR_RECALL_ON_DATA_ACCESS = 0x400000

DEFAULT_THRESHOLDS = {
    "min_words_per_minute": 40,
    "min_glossary_recall": 0.30,
    "min_latin_ratio": 0.05,
    "max_loop_ratio": 0.05,
    "spot_check_required": True,
    "spot_check_min": 10,
    "quote_window_seconds": 5,
    "min_quote_words": 3,
}

EVIDENCE_TYPES = {"promise", "exclusion", "trap", "emphasis", "solved_in_class"}
SPEAKERS = {"doctor", "ta", "slide"}
TS_RE = re.compile(r"^\[(\d+(?:\.\d+)?)\s*->\s*(\d+(?:\.\d+)?)\]\s*(.*)$")


def jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def norm(text):
    t = unicodedata.normalize("NFKC", str(text)).lower()
    t = re.sub(r"[ً-ٰٟـ]", "", t)
    t = re.sub("[أإآ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه")
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def thresholds(cfg):
    t = dict(DEFAULT_THRESHOLDS)
    t.update(cfg.get("thresholds", {}))
    return t


def parse_transcript(path):
    """Return list of (start, end, text). Accepts .jsonl or '[a -> b] text' lines."""
    segs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                d = json.loads(line)
                segs.append((float(d["start"]), float(d["end"]), d["text"]))
            else:
                m = TS_RE.match(line)
                if m:
                    segs.append((float(m.group(1)), float(m.group(2)), m.group(3)))
    return segs


def _p(course, rel):
    return os.path.join(course, rel)


# ---------------------------------------------------------------- hydrate
def gate_hydrate(course, cfg):
    msgs, ev = [], {"files": []}
    root = cfg.get("root", "")
    media = cfg.get("media", [])
    if not media:
        return False, ["HALT: course.json has no 'media' list (run inventory first)"], ev
    for item in media:
        vp = os.path.join(root, item["video"])
        if not os.path.isfile(vp):
            msgs.append("HALT: video missing: %s" % item["video"])
            continue
        size = os.path.getsize(vp)
        attrs = getattr(os.stat(vp), "st_file_attributes", 0)
        if size == 0:
            msgs.append("HALT: zero-byte video: %s" % item["video"])
            continue
        if attrs & (ATTR_OFFLINE | ATTR_RECALL_ON_OPEN | ATTR_RECALL_ON_DATA_ACCESS):
            msgs.append("HALT: cloud placeholder, not downloaded: %s" % item["video"])
            continue
        try:
            with open(vp, "rb") as f:
                head = f.read(1024)
                f.seek(size // 2)
                mid = f.read(1024)
                f.seek(max(0, size - 1024))
                tail = f.read(1024)
            if not (head and mid and tail):
                raise OSError("empty read")
        except OSError as exc:
            msgs.append("HALT: cannot read %s (%s)" % (item["video"], exc))
            continue
        ev["files"].append({"video": item["video"], "size": size})
    return (not msgs), msgs or ["all %d videos readable" % len(ev["files"])], ev


# ---------------------------------------------------------------- transcripts
def _metrics(segs, glossary):
    text = " ".join(s[2] for s in segs)
    tokens = text.split()
    words = len(tokens)
    dur_min = max(segs[-1][1], 1.0) / 60.0 if segs else 1.0
    latin = [t for t in tokens if re.search(r"[A-Za-z]", t)]
    latin_ratio = len(latin) / words if words else 0.0
    low = norm(text)
    hits = [g for g in glossary if norm(g) and norm(g) in low]
    recall = len(hits) / len(glossary) if glossary else 1.0
    loops = 0
    prev = None
    for _, _, t in segs:
        n = norm(t)
        ws = n.split()
        if n and n == prev:
            loops += 1
        elif ws and len(ws) >= 6 and max(ws.count(w) for w in set(ws)) >= len(ws) * 0.6:
            loops += 1
        prev = n
    loop_ratio = loops / len(segs) if segs else 1.0
    return {
        "words": words,
        "words_per_minute": round(words / dur_min, 1),
        "latin_ratio": round(latin_ratio, 3),
        "glossary_recall": round(recall, 3),
        "loop_ratio": round(loop_ratio, 3),
        "segments": len(segs),
    }


def gate_transcripts_exist(course, cfg):
    msgs, ev = [], {}
    for item in cfg.get("media", []):
        a, t = _p(course, item["audio"]), _p(course, item["transcript"])
        if not (os.path.isfile(a) and os.path.getsize(a) > 0):
            msgs.append("CRITICAL: audio missing/empty: %s (Stage 2 not executed)" % item["audio"])
        if not (os.path.isfile(t) and os.path.getsize(t) > 0):
            msgs.append("CRITICAL: transcript missing/empty: %s" % item["transcript"])
    return (not msgs), msgs or ["audio + transcript exist for all media"], ev


ASR_HALLUCINATIONS = ["نانسي قنقر", "ترجمة نانسي قنقر", "المترجمات للمشاهدة", "المترجم لمترجمات", "اشتركوا في القناة",
                      "شكرا للمشاهدة", "شكراً للمشاهدة", "subtitles by", "thanks for watching", "amara.org"]


def hallucinated_segments(segs):
    return [s for s in segs if any(h.lower() in s[2].lower() for h in ASR_HALLUCINATIONS)]


def _slide_text(cfg, rels):
    import warnings
    warnings.filterwarnings("ignore")
    import fitz
    out = []
    for rel in rels:
        doc = fitz.open(os.path.join(cfg.get("root", ""), rel))
        out.append(" ".join(pg.get_text() for pg in doc))
    return norm(" ".join(out))


def section_glossary(cfg, item, glossary):
    """Glossary terms that occur in this media item's own slides (item['slides']); whole glossary if none listed.
    Returns (terms, error_or_None)."""
    rels = item.get("slides")
    if not rels:
        return glossary, None
    try:
        text = _slide_text(cfg, rels)
    except Exception as exc:
        return [], "cannot read slides %s (%s)" % (rels, exc)
    terms = [g for g in glossary if norm(g) and norm(g) in text]
    if len(terms) < 5:
        return [], "only %d glossary terms occur in %s; add terms from these slides (need >= 5)" % (len(terms), rels)
    return terms, None


def english_only_runs(segs, min_words=25):
    """Runs of consecutive segments with no Arabic letters and >= min_words words in total: in an Arabic lecture
    this is almost always ASR translating the speech to English. Short English runs (terms) are normal."""
    runs, cur = [], []
    for s in segs:
        if not re.search(r"[؀-ۿ]", s[2]) and len(s[2].split()) >= 4:
            cur.append(s)
        else:
            if cur: runs.append(cur)
            cur = []
    if cur: runs.append(cur)
    return [r for r in runs if sum(len(x[2].split()) for x in r) >= min_words]


def has_foreign_script(segs):
    return [s for s in segs if re.search(r"[⺀-鿿가-힯Ѐ-ӿ]", s[2])]


def gate_transcript_quality(course, cfg):
    th = thresholds(cfg)
    msgs, ev = [], {"metrics": {}}
    gpath = _p(course, cfg.get("glossary", "glossary.txt"))
    if not os.path.isfile(gpath):
        return False, ["CRITICAL: glossary file missing: %s" % cfg.get("glossary", "glossary.txt")], ev
    with open(gpath, encoding="utf-8") as f:
        glossary = [ln.strip() for ln in f if ln.strip()]
    if len(glossary) < 5:
        return False, ["CRITICAL: glossary has fewer than 5 terms"], ev
    for item in cfg.get("media", []):
        tp = _p(course, item["transcript"])
        if not os.path.isfile(tp):
            msgs.append("CRITICAL: transcript missing: %s" % item["transcript"])
            continue
        segs = parse_transcript(tp)
        if not segs:
            msgs.append("CRITICAL: transcript has no timestamped segments: %s" % item["transcript"])
            continue
        terms, err = section_glossary(cfg, item, glossary)
        if err:
            msgs.append("QUALITY: %s: %s" % (item["transcript"], err))
            continue
        m = _metrics(segs, terms)
        m["glossary_terms_used"] = len(terms)
        ev["metrics"][item["transcript"]] = m
        for r in english_only_runs(segs):
            msgs.append("QUALITY: %s %.0f-%.0fs is a long English-only passage (%d words): likely ASR translation; run scripts/repair_transcripts.py" % (item["transcript"], r[0][0], r[-1][1], sum(len(x[2].split()) for x in r)))
        fs = has_foreign_script(segs)
        if fs:
            msgs.append("QUALITY: %s has %d segments with non-Arabic/non-Latin characters (first at %.0fs)" % (item["transcript"], len(fs), fs[0][0]))
        bad = hallucinated_segments(segs)
        if bad:
            msgs.append("QUALITY: %s has %d known ASR hallucination lines (e.g. '%s' at %.0fs); run scripts/clean_transcripts.py" % (item["transcript"], len(bad), bad[0][2][:40], bad[0][0]))
        if m["words_per_minute"] < th["min_words_per_minute"]:
            msgs.append("QUALITY: %s words/min %.1f < %s" % (item["transcript"], m["words_per_minute"], th["min_words_per_minute"]))
        if m["glossary_recall"] < th["min_glossary_recall"]:
            msgs.append("QUALITY: %s glossary recall %.2f < %s (technical terms garbled or missing)" % (item["transcript"], m["glossary_recall"], th["min_glossary_recall"]))
        if m["latin_ratio"] < th["min_latin_ratio"]:
            msgs.append("QUALITY: %s English-word share %.3f < %s (mixed Arabic/English lecture transcribed as pure Arabic?)" % (item["transcript"], m["latin_ratio"], th["min_latin_ratio"]))
        if m["loop_ratio"] > th["max_loop_ratio"]:
            msgs.append("QUALITY: %s repetition-loop ratio %.3f > %s" % (item["transcript"], m["loop_ratio"], th["max_loop_ratio"]))
    if th["spot_check_required"]:
        sp = _p(course, "_audit/spot_check.json")
        if not os.path.isfile(sp):
            msgs.append("QUALITY: _audit/spot_check.json missing (human must listen to %d moments)" % th["spot_check_min"])
        else:
            entries = jload(sp).get("entries", [])
            good = [e for e in entries if e.get("ok") is True and e.get("media") and isinstance(e.get("t"), (int, float))]
            if len(good) < th["spot_check_min"] or len(good) != len(entries):
                msgs.append("QUALITY: spot check needs >= %d entries, all ok=true (got %d valid of %d)" % (th["spot_check_min"], len(good), len(entries)))
    return (not msgs), msgs or ["transcript quality metrics within thresholds"], ev


# ---------------------------------------------------------------- evidence
def load_evidence(course):
    path = _p(course, "evidence.jsonl")
    items = []
    if not os.path.isfile(path):
        return None, ["CRITICAL: evidence.jsonl missing"]
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except ValueError:
                return None, ["CRITICAL: evidence.jsonl line %d is not valid JSON" % i]
    return items, []


def gate_evidence(course, cfg):
    th = thresholds(cfg)
    items, errs = load_evidence(course)
    if items is None:
        return False, errs, {}
    msgs, seen = [], set()
    by_media = {m["video"]: m["transcript"] for m in cfg.get("media", [])}
    cache = {}
    if not items:
        return False, ["CRITICAL: evidence.jsonl is empty"], {}
    for e in items:
        eid = e.get("id", "?")
        for key in ("id", "claim", "type", "kind", "quote", "speaker", "confidence"):
            if key not in e or e[key] in ("", None):
                msgs.append("%s: missing field '%s'" % (eid, key))
        if eid in seen:
            msgs.append("%s: duplicate id" % eid)
        seen.add(eid)
        if e.get("type") not in EVIDENCE_TYPES:
            msgs.append("%s: bad type %r" % (eid, e.get("type")))
        if e.get("speaker") not in SPEAKERS:
            msgs.append("%s: speaker must be one of %s" % (eid, sorted(SPEAKERS)))
        if len(norm(e.get("quote", "")).split()) < th["min_quote_words"]:
            msgs.append("%s: quote shorter than %d words" % (eid, th["min_quote_words"]))
            continue
        q = norm(e.get("quote", ""))
        if e.get("kind") == "video":
            ts, te = e.get("t_start"), e.get("t_end")
            if not isinstance(ts, (int, float)) or not isinstance(te, (int, float)) or te <= ts:
                msgs.append("%s: video evidence needs numeric t_start < t_end" % eid)
                continue
            tr = by_media.get(e.get("media"))
            if not tr:
                msgs.append("%s: media %r not in course.json" % (eid, e.get("media")))
                continue
            if tr not in cache:
                cache[tr] = parse_transcript(_p(course, tr))
            w = th["quote_window_seconds"]
            window = norm(" ".join(s[2] for s in cache[tr] if s[1] >= ts - w and s[0] <= te + w))
            if q not in window:
                msgs.append("%s: quote not found in transcript within %s-%ss" % (eid, ts, te))
        elif e.get("kind") == "pdf":
            page, fpath = e.get("page"), e.get("file")
            if not isinstance(page, int) or not fpath:
                msgs.append("%s: pdf evidence needs file + integer page" % eid)
                continue
            try:
                import fitz  # PyMuPDF
                with fitz.open(os.path.join(cfg.get("root", ""), fpath)) as doc:
                    text = norm(doc[page - 1].get_text())
                if q not in text:
                    msgs.append("%s: quote not found on page %d of %s" % (eid, page, fpath))
            except Exception as exc:  # noqa: BLE001
                msgs.append("%s: cannot check pdf (%s)" % (eid, exc))
        else:
            msgs.append("%s: kind must be 'video' or 'pdf'" % eid)
    return (not msgs), msgs or ["%d evidence items verified against sources" % len(items)], {"count": len(items)}


# ---------------------------------------------------------------- ledger / verify
def gate_ledger(course, cfg):
    lp = _p(course, "course_curriculum_ledger.json")
    if not os.path.isfile(lp):
        return False, ["CRITICAL: course_curriculum_ledger.json missing"], {}
    ledger = jload(lp)
    items, _ = load_evidence(course)
    ids = {e["id"] for e in (items or []) if "id" in e}
    msgs, counts = [], {"problems": 0, "theory": 0, "formulas": 0}
    if not ledger.get("modules"):
        return False, ["CRITICAL: ledger has no modules"], {}
    for mod in ledger["modules"]:
        for t in mod.get("theory_items", []):
            counts["theory"] += 1
            if not t.get("source"):
                msgs.append("%s: theory item without source" % t.get("id"))
        for f in mod.get("formulas", []):
            counts["formulas"] += 1
            if not f.get("source") and not f.get("evidence_ids"):
                msgs.append("%s: formula without source" % f.get("id"))
        for p in mod.get("problems", []):
            counts["problems"] += 1
            pid = p.get("id")
            if not p.get("source_file") or not p.get("page_or_slide"):
                msgs.append("%s: problem without source_file/page_or_slide" % pid)
            oral = p.get("solved_by_instructor") or p.get("instructor_context")
            eids = p.get("evidence_ids", [])
            if oral and not eids:
                msgs.append("%s: claims instructor said/solved it but has no evidence_ids" % pid)
            for eid in eids:
                if eid not in ids:
                    msgs.append("%s: evidence id %s not in evidence.jsonl" % (pid, eid))
    return (not msgs), msgs or ["ledger: %(problems)d problems, %(theory)d theory, %(formulas)d formulas all sourced" % counts], counts


def gate_verify(course, cfg):
    rp = _p(course, "_verify/results.json")
    if not os.path.isfile(rp):
        return False, ["CRITICAL: _verify/results.json missing (SymPy checks were not run)"], {}
    checks = {c["id"]: c.get("ok") for c in jload(rp).get("checks", [])}
    lp = _p(course, "course_curriculum_ledger.json")
    msgs = []
    if os.path.isfile(lp):
        for mod in jload(lp).get("modules", []):
            for p in mod.get("problems", []):
                if p.get("sympy_verified"):
                    if checks.get(p["id"]) is not True:
                        msgs.append("%s: marked sympy_verified but no passing check in results.json" % p["id"])
    bad = [k for k, v in checks.items() if v is not True]
    for k in bad:
        msgs.append("check %s failed" % k)
    if not checks:
        msgs.append("results.json has no checks")
    return (not msgs), msgs or ["%d SymPy checks passing" % len(checks)], {"checks": len(checks)}


# ---------------------------------------------------------------- freshness
def gate_freshness(course, cfg):
    """Deliverables must be newer than every input they depend on (catches 'built before transcripts')."""
    deliv = cfg.get("deliverables", [])
    if not deliv:
        return False, ["CRITICAL: course.json lists no deliverables"], {}
    inputs = [_p(course, m["transcript"]) for m in cfg.get("media", [])]
    inputs += [_p(course, "evidence.jsonl"), _p(course, "course_curriculum_ledger.json")]
    newest = max(os.path.getmtime(p) for p in inputs if os.path.isfile(p))
    msgs = []
    for d in deliv:
        dp = _p(course, d)
        if not os.path.isfile(dp):
            msgs.append("deliverable missing: %s" % d)
        elif os.path.getmtime(dp) < newest:
            msgs.append("STALE: %s was built before the newest transcript/evidence/ledger" % d)
    return (not msgs), msgs or ["all deliverables newer than their inputs"], {}


def gate_preflight(course, cfg):
    """Re-runs the preflight logic (cannot be faked by writing a file). Environment is checked at preflight time."""
    import preflight  # local import: preflight imports gates
    res, _ = preflight.run(course, cfg, write=False, check_env=False)
    msgs = []
    if res["autofilled"]:
        msgs.append("values were auto-detected but not saved to course.json (%s): run scripts/preflight.py" % ", ".join(res["autofilled"]))
    for i in res["items"]:
        if i["status"] in ("missing", "ambiguous") and i["kind"] in ("blocking", "quality", "recommended"):
            msgs.append("%s: %s (%s)" % (i["id"], i["status"], i["detail"]))
    return (not msgs), msgs or ["preflight: nothing missing"], {"status": res["status"]}


GATES = [
    ("preflight", gate_preflight),
    ("hydrate", gate_hydrate),
    ("transcripts_exist", gate_transcripts_exist),
    ("transcript_quality", gate_transcript_quality),
    ("evidence", gate_evidence),
    ("ledger", gate_ledger),
    ("verify", gate_verify),
]
