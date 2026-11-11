"""Self-test for the gatekeeper. Run: python tests/run_tests.py

Builds a good fixture course (must PASS) and then breaks it in eight ways (each must FAIL).
If any broken fixture passes, the gatekeeper is too lenient and the skill must not be used.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATE = os.path.join(HERE, "..", "scripts", "validate.py")

GLOSSARY = ["amplifier", "voltage gain", "input resistance", "output resistance", "op amp", "feedback",
            "bandwidth", "cutoff frequency", "common mode", "bias"]


def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def make_good(d):
    root = os.path.join(d, "teams")
    os.makedirs(os.path.join(root, "Sections"))
    with open(os.path.join(root, "Sections", "s1.mp4"), "wb") as f:
        f.write(b"\x00\x00\x00\x18ftypmp42" + os.urandom(4096))
    course = os.path.join(d, "course")
    os.makedirs(course)
    os.makedirs(os.path.join(root, "Class Materials"))
    for name in ("Lecture1.pdf", "Summary_Questions.pdf"):
        with open(os.path.join(root, "Class Materials", name), "wb") as f:
            f.write(b"%PDF-1.4 fake")
    cfg = {
        "course_code": "ECE321", "course_name": "Electronic Circuits",
        "exam": {"date": "2026-11-12"}, "calibration": "none",
        "root": root,
        "glossary": "glossary.txt",
        "media": [{"video": "Sections/s1.mp4", "audio": "_audio/s1.mp3", "transcript": "_audio/s1_transcript.txt"}],
        "deliverables": ["capsule.pdf"],
    }
    w(os.path.join(course, "course.json"), json.dumps(cfg))
    w(os.path.join(course, "glossary.txt"), "\n".join(GLOSSARY))
    with open(os.path.join(course, "_audio", "s1.mp3") if os.path.isdir(os.path.join(course, "_audio")) else os.path.join(course, "s1.mp3"), "wb") as f:
        pass
    os.makedirs(os.path.join(course, "_audio"), exist_ok=True)
    with open(os.path.join(course, "_audio", "s1.mp3"), "wb") as f:
        f.write(os.urandom(2048))
    lines = []
    for i in range(10):
        t0 = i * 6
        lines.append("[%d.00 -> %d.00] في الـ amplifier رقم %d بنحسب الـ voltage gain من الـ input resistance والـ output resistance مع feedback و bias" % (t0, t0 + 6, i))
    w(os.path.join(course, "_audio", "s1_transcript.txt"), "\n".join(lines) + "\n")
    w(os.path.join(course, "_audit", "spot_check.json"),
      json.dumps({"entries": [{"media": "Sections/s1.mp4", "t": 6 * i, "ok": True} for i in range(10)]}))
    ev = {"id": "EV-01", "claim": "doctor stressed gain with loading", "type": "emphasis", "kind": "video",
          "media": "Sections/s1.mp4", "t_start": 12, "t_end": 18,
          "quote": "بنحسب الـ voltage gain من الـ input resistance", "speaker": "ta", "confidence": 0.8}
    w(os.path.join(course, "evidence.jsonl"), json.dumps(ev, ensure_ascii=False) + "\n")
    ledger = {"modules": [{"module_id": "MOD-01", "title": "Amps",
                           "theory_items": [{"id": "THEORY-01", "source": "lec1.pdf | p2"}],
                           "formulas": [{"id": "LAW-01", "source": "lec1.pdf | p3"}],
                           "problems": [{"id": "PROB-01", "title": "Mic and speaker", "source_file": "sheet.pdf",
                                         "page_or_slide": 4, "solved_by_instructor": True,
                                         "evidence_ids": ["EV-01"], "sympy_verified": True,
                                         "recurrence_sources": ["a", "b"]}]}]}
    w(os.path.join(course, "course_curriculum_ledger.json"), json.dumps(ledger))
    w(os.path.join(course, "_verify", "results.json"), json.dumps({"checks": [{"id": "PROB-01", "ok": True}]}))
    # deliverable built AFTER all inputs
    time.sleep(0.05)
    w(os.path.join(course, "capsule.pdf"), "pdf")
    return course


def run(course, post=True):
    cmd = [sys.executable, VALIDATE, course] + (["--post-build"] if post else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout


def edit_json(path, fn):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    fn(d)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)


def case_no_audio(c):
    os.remove(os.path.join(c, "_audio", "s1.mp3"))


def case_garbled_transcript(c):
    lines = ["[%d.00 -> %d.00] نحن نتحدث عن المخصصة مع المخصصة في الامليفار رقم %d" % (i * 6, i * 6 + 6, i) for i in range(10)]
    w(os.path.join(c, "_audio", "s1_transcript.txt"), "\n".join(lines) + "\n")


def case_asr_hallucination(c):
    with open(os.path.join(c, "_audio", "s1_transcript.txt"), "a", encoding="utf-8") as f:
        f.write("[60.00 -> 90.00] ترجمة نانسي قنقر" + chr(10))


def case_unreadable_slides(c):
    # per-section glossary needs real slide text; scanned/unreadable slides must fail, never pass silently
    edit_json(os.path.join(c, "course.json"),
              lambda d: d["media"][0].update({"slides": ["Class Materials/Lecture1.pdf"]}))


def case_english_translation_passage(c):
    # ASR translated a stretch of the Arabic lecture to English: long English-only run must fail
    with open(os.path.join(c, "_audio", "s1_transcript.txt"), "a", encoding="utf-8") as f:
        for i in range(4):
            f.write("[%d.00 -> %d.00] now I want the output voltage and I take the input to the other side of the rule" % (60 + 6 * i, 66 + 6 * i) + chr(10))


def case_foreign_script(c):
    with open(os.path.join(c, "_audio", "s1_transcript.txt"), "a", encoding="utf-8") as f:
        f.write("[60.00 -> 66.00] output " + chr(0x5916) + " of stage one" + chr(10))


def case_quote_not_in_transcript(c):
    p = os.path.join(c, "evidence.jsonl")
    d = json.loads(open(p, encoding="utf-8").read())
    d["quote"] = "the doctor promised this exact problem in the exam"
    w(p, json.dumps(d, ensure_ascii=False) + "\n")


def case_no_timestamp(c):
    p = os.path.join(c, "evidence.jsonl")
    d = json.loads(open(p, encoding="utf-8").read())
    del d["t_start"]
    w(p, json.dumps(d, ensure_ascii=False) + "\n")


def case_oral_claim_without_evidence(c):
    edit_json(os.path.join(c, "course_curriculum_ledger.json"),
              lambda d: d["modules"][0]["problems"][0].update({"evidence_ids": []}))


def case_unverified_math(c):
    w(os.path.join(c, "_verify", "results.json"), json.dumps({"checks": [{"id": "OTHER", "ok": True}]}))


def case_stale_deliverable(c):
    old = time.time() - 3600
    os.utime(os.path.join(c, "capsule.pdf"), (old, old))


def case_no_spot_check(c):
    os.remove(os.path.join(c, "_audit", "spot_check.json"))


BAD = [case_no_audio, case_garbled_transcript, case_asr_hallucination, case_unreadable_slides, case_english_translation_passage, case_foreign_script, case_quote_not_in_transcript, case_no_timestamp,
       case_oral_claim_without_evidence, case_unverified_math, case_stale_deliverable, case_no_spot_check]


PREFLIGHT = os.path.join(HERE, "..", "scripts", "preflight.py")


def run_pf(course, args=(), env=None):
    r = subprocess.run([sys.executable, PREFLIGHT, course] + list(args), capture_output=True, text=True,
                       encoding="utf-8", env=env)
    try:
        data = json.loads(r.stdout)
    except ValueError:
        data = {}
    return r.returncode, data, r.stdout


def preflight_tests(tmp):
    """Returns a list of (name, ok, detail)."""
    res = []

    def cfgp(c):
        return os.path.join(c, "course.json")

    # A. complete course -> zero questions
    c = make_good(os.path.join(tmp, "pf_good"))
    code, d, _ = run_pf(c)
    res.append(("preflight: complete course asks nothing", code == 0 and d.get("questions") == [], "exit %s questions %s" % (code, d.get("questions"))))

    # B. root missing -> exactly one question: root
    c = make_good(os.path.join(tmp, "pf_noroot"))
    edit_json(cfgp(c), lambda x: (x.pop("root"), x.update({"discover_roots": []})))
    code, d, _ = run_pf(c, ["--no-env"])
    ids = [q["id"] for q in d.get("questions", [])]
    res.append(("preflight: missing root -> asks only 'root'", code == 3 and ids == ["root"], "exit %s ids %s" % (code, ids)))

    # C. two candidate folders -> one question with 2 options
    c = make_good(os.path.join(tmp, "pf_ambig"))
    parent = os.path.join(tmp, "pf_ambig_parent")
    os.makedirs(os.path.join(parent, "Fall-E-Electronic Circuits-A"))
    os.makedirs(os.path.join(parent, "Spring-E-Electronic Circuits-B"))
    edit_json(cfgp(c), lambda x: (x.pop("root"), x.pop("media"), x.update({"discover_roots": [parent]})))
    code, d, _ = run_pf(c, ["--no-env"])
    qs = d.get("questions", [])
    res.append(("preflight: ambiguous folders -> choice question", code == 3 and len(qs) == 1 and len(qs[0].get("options", [])) == 2, "exit %s questions %s" % (code, [q["id"] for q in qs])))

    # D. ffmpeg missing -> blocked (exit 1) with a clear instruction
    c = make_good(os.path.join(tmp, "pf_noffmpeg"))
    empty = os.path.join(tmp, "emptybin")
    os.makedirs(empty, exist_ok=True)
    env = dict(os.environ, PATH=empty)
    code, d, out = run_pf(c, env=env)
    res.append(("preflight: ffmpeg missing -> blocked", code == 1 and "ffmpeg" in out, "exit %s" % code))

    # E. calibration missing -> one recommended question; answer once; never asked again
    c = make_good(os.path.join(tmp, "pf_calib"))
    edit_json(cfgp(c), lambda x: x.pop("calibration"))
    code1, d1, _ = run_pf(c, ["--no-env"])
    ids1 = [q["id"] for q in d1.get("questions", [])]
    code2, d2, _ = run_pf(c, ["--no-env", "--answer", "calibration=none"])
    code3, d3, _ = run_pf(c, ["--no-env"])
    ok = code1 == 3 and ids1 == ["calibration"] and code2 == 0 and code3 == 0 and d3.get("questions") == []
    res.append(("preflight: answer is saved, never asked twice", ok, "codes %s %s %s ids %s" % (code1, code2, code3, ids1)))

    # F. secrets: key checked by name only, value never printed or stored
    c = make_good(os.path.join(tmp, "pf_secret"))
    secret = "SENTINEL_SECRET_123"
    env = dict(os.environ, GROQ_API_KEY=secret)
    code, d, out = run_pf(c, env=env)
    stored = open(cfgp(c), encoding="utf-8").read() + open(os.path.join(c, "_audit", "preflight.json"), encoding="utf-8").read()
    res.append(("preflight: secret value never printed or stored", secret not in out and secret not in stored, "exit %s" % code))

    # G. never more than 3 questions, blocking first
    c = os.path.join(tmp, "pf_empty")
    os.makedirs(c)
    w(cfgp(c), json.dumps({"discover_roots": []}))
    code, d, _ = run_pf(c, ["--no-env"])
    qs = d.get("questions", [])
    res.append(("preflight: at most 3 questions, blocking first", code == 3 and 0 < len(qs) <= 3 and all(q["kind"] == "blocking" for q in qs), "exit %s ids %s" % (code, [q["id"] for q in qs])))
    return res


def tool_tests(tmp):
    """draft_evidence / review_links / score_topics extras. Each returns (name, ok, detail)."""
    res = []
    S = os.path.join(HERE, "..", "scripts")
    def sh(script, c, *extra):
        r = subprocess.run([sys.executable, os.path.join(S, script), c] + list(extra), capture_output=True, text=True, encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        return r.returncode, r.stdout or ""
    c = make_good(os.path.join(tmp, "tools"))
    tp = os.path.join(c, "_audio", "s1_transcript.txt")
    with open(tp, "a", encoding="utf-8") as f:
        f.write("[60.00 -> 66.00] السؤال ده هييجي في الامتحان أكيد" + chr(10))
    code, out = sh("draft_evidence.py", c)
    cand = json.load(open(os.path.join(c, "_audit", "evidence_candidates.json"), encoding="utf-8"))
    text = open(tp, encoding="utf-8").read()
    res.append(("draft_evidence: finds signal, quote verbatim", code == 0 and len(cand) == 1 and cand[0]["quote"] in text
                and cand[0]["suggested_type"] == "promise", "exit %s n=%d" % (code, len(cand))))
    res.append(("draft_evidence: writes no evidence", "EV-02" not in open(os.path.join(c, "evidence.jsonl"), encoding="utf-8").read(), ""))
    code, out = sh("review_links.py", c)   # fixture: title 'Mic and speaker' vs claim 'doctor stressed gain...' share nothing
    res.append(("review_links: unrelated link without basis fails", code == 1 and "WEAK LINK" in out, "exit %s" % code))
    lp = os.path.join(c, "course_curriculum_ledger.json")
    edit_json(lp, lambda d: d["modules"][0]["problems"][0].update({"link_basis": "TA solves this sheet problem at 12 s"}))
    code, out = sh("review_links.py", c)
    res.append(("review_links: written link_basis passes", code == 0, "exit %s" % code))
    edit_json(lp, lambda d: d["modules"][0]["problems"][0].update({"in_question_bank": True}))
    code, out = sh("score_topics.py", c)
    res.append(("score_topics: all-in-bank bonus skipped", code == 0 and "does not discriminate" in out, "exit %s" % code))
    edit_json(os.path.join(c, "course.json"), lambda d: d.update({"scoring_overrides": {"weights": {"emphasis": 10.0}}}))
    code, out = sh("score_topics.py", c)
    rk = json.load(open(os.path.join(c, "ranking.json"), encoding="utf-8"))
    res.append(("score_topics: pct present, 0-100", all(0 <= r.get("pct", -1) <= 100 for r in rk) and rk[0]["pct"] > 50, "pct %s" % (rk[0].get("pct") if rk else None)))
    res.append(("score_topics: per-course weight override applies", code == 0 and rk and rk[0]["score"] == 7.0, "score %s" % (rk[0]["score"] if rk else None)))
    r = subprocess.run([sys.executable, os.path.join(S, "run_all.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    res.append(("run_all: usage error without a course", r.returncode == 2, "exit %s" % r.returncode))
    # build_capsule: gated, real source page rendered, strict about missing steps/sources
    c = make_good(os.path.join(tmp, "build"))
    root = json.load(open(os.path.join(c, "course.json"), encoding="utf-8"))["root"]
    try:
        import fitz
        d = fitz.open()
        for k in range(5):
            d.new_page().insert_text((72, 72), "page %d question" % (k + 1))
        d.save(os.path.join(root, "Class Materials", "sheet.pdf"))
        d.close()
        have_fitz = True
    except ImportError:
        have_fitz = False
    lp = os.path.join(c, "course_curriculum_ledger.json")
    code, out = sh("build_capsule.py", c)
    res.append(("build_capsule: no term_map.json -> fails", code == 1 and "term_map.json" in out, "exit %s" % code))
    w(os.path.join(c, "term_map.json"), json.dumps({"المقاومة": "resistance"}, ensure_ascii=False))
    code, out = sh("build_capsule.py", c)
    res.append(("build_capsule: no solution -> fails", code == 1 and "no solution_tex/solution_steps" in out, "exit %s" % code))
    def full(d):
        m = d["modules"][0]
        m["theory_items"][0]["explain_ar"] = "شرح المفهوم"
        m["formulas"][0].update({"tex": r"a=\frac{b}{c}", "symbols_ar": "الرموز والوحدات", "when_ar": "متى تنطبق"})
        m["problems"][0].update({"solution_tex": [r"a=\frac{b}{c}", "c=d"], "steps_ar": ["الخطوة الأولى بالعربي", "الخطوة التانية"],
                                 "explain_ar": "المطلوب كذا والقانون كذا", "mistakes_ar": ["غلطة شائعة"],
                                 "source_ref": "Sheet 9 · Q4", "lecture_refs": ["Lec 7 · slide 12"], "givens_tex": [r"k=1"], "insight_ar": ["الفكرة كذا", "الطريقة كذا", "الفخ كذا"], "insight_laws": [{"tex": r"V=IR", "note_ar": "قانون اوم", "note_en": "Ohm law"}], "parts": [{"ask_ar": "المطلوب الأول", "ask_en": "First ask", "how_ar": "نطبق القانون", "how_en": "apply the law", "steps": [0, 0], "answer_tex": r"x=1"},
                                                                    {"ask_ar": "المطلوب التاني", "ask_en": "Second ask", "how_ar": "نحسب", "how_en": "compute", "steps": [1, 1], "answer_tex": r"y=2"}]})
    edit_json(lp, lambda d: d["modules"][0]["problems"][0].update({"solution_steps": ["a = b + c"]}))
    code, out = sh("build_capsule.py", c)
    res.append(("build_capsule: formula without symbols_ar/when_ar -> fails", code == 1 and "symbols_ar" in out, "exit %s" % code))
    if have_fitz:
        edit_json(lp, full)
        code, out = sh("build_capsule.py", c, "--exam", "1")
        bd = os.path.join(c, "build")
        def rd(n):
            q = os.path.join(bd, n)
            return open(q, encoding="utf-8").read() if os.path.isfile(q) else ""
        fq, th, qs = rd("ECE321_Electronic_Circuits_Formulas.html"), rd("ECE321_Electronic_Circuits_Theory.html"), rd("ECE321_Electronic_Circuits_Solved_Questions_AR.html")
        res.append(("build_capsule: formulas file has symbols and when-it-applies", code == 0 and "الرموز والوحدات" in fq and "متى تنطبق" in fq, "exit %s" % code))
        res.append(("build_capsule: theory file explains each concept", "شرح المفهوم" in th, ""))
        res.append(("build_capsule: questions file = image + every step explained + practice paper",
                    "PROB-01_p4.png" in qs and "الخطوة الأولى بالعربي" in qs and "غلطة شائعة" in qs and "الإجابة النموذجية" in qs and "Question 1" in qs,
                    "exit %s" % code))
        res.append(("build_capsule: bundled offline KaTeX copied", os.path.isfile(os.path.join(bd, "katex", "katex.min.js")), ""))
        res.append(("questions file: Givens first, each requirement then its answer", "المعطيات" in qs and "المطلوب التاني" in qs and qs.index("المعطيات") < qs.index("المطلوب الأول") < qs.index("x=1") < qs.index("المطلوب التاني") < qs.index("y=2"), ""))
        edit_json(lp, lambda d: d["modules"][0]["problems"][0].update({"parts": [{"ask_ar": "x", "ask_en": "x", "how_ar": "x", "how_en": "x", "steps": [0, 0], "answer_tex": "x"}]}))
        code, out = sh("build_capsule.py", c)
        res.append(("build_capsule: parts not covering every step -> fails", code == 1 and "cover every solution_tex line" in out, "exit %s" % code))
        edit_json(lp, full)
        edit_json(lp, lambda d: d["modules"][0]["problems"][0].update({"steps_ar": ["واحدة بس"]}))
        code, out = sh("build_capsule.py", c)
        res.append(("questions + master show problem number, page and lecture slide", "Sheet 9 · Q4" in qs and "Lec 7 · slide 12" in qs and "Sheet 9 · Q4" in rd("ECE321_Electronic_Circuits_Master_Capsule_AR.html") if os.path.isfile(os.path.join(bd, "ECE321_Electronic_Circuits_Master_Capsule_AR.html")) else "Sheet 9 · Q4" in qs, ""))
        edit_json(lp, lambda d: d["modules"][0]["problems"][0].update({"explain_ar": "نحسب المقاومة هنا"}))
        code, out = sh("build_capsule.py", c)
        res.append(("language rule: Arabic course term in an explanation -> fails", code == 1 and "resistance" in out and "explain_ar" in out, "exit %s" % code))
        edit_json(lp, full)
        res.append(("build_capsule: steps_ar length mismatch -> fails", code == 1 and "steps_ar" in out, "exit %s" % code))
        edit_json(lp, full)
        code, out = sh("build_master.py", c)
        mt = rd("ECE321_Electronic_Circuits_Master_Capsule_AR.html")
        res.append(("build_master: one combined file with sections, image and Arabic note", code == 0 and "القسم الثاني" in mt and "PROB-01_p4.png" in mt and "المطلوب كذا" in mt, "exit %s" % code))
        res.append(("build_master: capsule explanation box (insight) under every problem, with the laws used", "شرح الكبسولة للمسألة" in mt and "القوانين المستخدمة" in mt and "قانون اوم" in mt, ""))
        edit_json(lp, lambda d: d["modules"][0]["problems"][0].pop("insight_ar"))
        code, out = sh("build_master.py", c)
        sys.path.insert(0, S)
        import review_explanations as _rv
        _led = {"modules": [{"problems": [{"id": "P1", "title": "t", "explain_en": "e", "steps_en": ["s"], "parts": [{"ask_en": "a", "answer_tex": "x", "how_en": "h"}], "insight_laws": [{"note_en": "n"}]}]}]}
        _rep = _rv.review(_led, lambda pr, pl, md: '{"verdict": "issues", "issues": [{"where": "s", "problem": "wrong", "suggestion": "fix"}]}', "stub")
        _ok = _rv.review(_led, lambda pr, pl, md: '```json' + chr(10) + '{"verdict": "ok", "issues": []}' + chr(10) + '```', "stub")
        _bad = _rv.review(_led, lambda pr, pl, md: "not json", "stub")
        res.append(("review_explanations: issues are recorded, ok passes, a non-JSON reply is an error (never silently ok)",
                    _rep["problems"]["P1"]["verdict"] == "issues" and _ok["problems"]["P1"]["verdict"] == "ok" and _bad["problems"]["P1"]["verdict"] == "error"
                    and "explanation" in _rv.build_payload(_led["modules"][0]["problems"][0]), ""))
        r_ = subprocess.run([sys.executable, os.path.join(S, "review_explanations.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        res.append(("review_explanations: usage error without a course", r_.returncode == 2, "exit %s" % r_.returncode))
        res.append(("bidi: English runs inside Arabic text are isolated, math untouched, insight box sits under the Given",
                    '<span class="ltr">' in mt and mt.find("المعطيات") < mt.find("شرح الكبسولة للمسألة") < mt.find("المطلوب <span"), ""))
        res.append(("build_master: how-to-solve line under every requirement", "طريقة حل المطلوب" in mt and "نطبق القانون" in mt, ""))
        res.append(("build_master: missing insight_ar -> fails", code == 1 and "insight_ar" in out, "exit %s" % code))
        edit_json(lp, full)
        res.append(("build_master: every problem shows its explanation box and per-step Arabic lines under the solution", "فهم المسألة قبل الحل" in mt and '<div class="ar">' in mt and "الإجابة" in mt, ""))
        code, out = sh("build_master.py", c, "--lang", "en")
        res.append(("build_master --lang en: missing explain_en -> fails", code == 1 and "explain_en" in out, "exit %s" % code))
        edit_json(lp, lambda d: d["modules"][0]["problems"][0].update({"explain_en": "What is asked and which law", "insight_en": ["the idea", "the method", "the trap"], "steps_en": ["first step", "second step"], "mistakes_en": ["a common slip"]}))
        code, out = sh("build_master.py", c, "--lang", "both")
        en = rd("ECE321_Electronic_Circuits_Master_Capsule_EN.html")
        res.append(("build_master --lang both: English file is LTR with English labels", code == 0 and "dir=ltr" in en and "Part 2" in en and "What is asked" in en and "القسم الثاني" not in en and "القسم الثاني" in rd("ECE321_Electronic_Circuits_Master_Capsule_AR.html"), "exit %s" % code))
        code, out = sh("build_capsule.py", c, "--lang", "both")
        qe = rd("ECE321_Electronic_Circuits_Solved_Questions_EN.html")
        res.append(("build_capsule --lang both: English questions file", code == 0 and "first step" in qe and "Common mistakes" in qe and "a common slip" in qe and "الخطوة الأولى بالعربي" in rd("ECE321_Electronic_Circuits_Solved_Questions_AR.html"), "exit %s" % code))
        code, out = sh("build_capsule.py", c, "--pdf")
        code2, out2 = sh("build_master.py", c)
        dest = os.path.join(tmp, "packaged")
        code3, out3 = sh("package_output.py", c, "--dest", dest)
        pk = os.path.join(dest, "ECE321_Electronic_Circuits")
        res.append(("package_output: course folder with PDF/ (four PDFs) and HTML/ (+img, katex)",
                    code3 == 0 and all(os.path.isfile(os.path.join(pk, "PDF", n)) for n in ("ECE321_Electronic_Circuits_Master_Capsule_AR.pdf", "ECE321_Electronic_Circuits_Formulas.pdf", "ECE321_Electronic_Circuits_Theory.pdf", "ECE321_Electronic_Circuits_Solved_Questions_AR.pdf"))
                    and os.path.isfile(os.path.join(pk, "HTML", "ECE321_Electronic_Circuits_Master_Capsule_AR.html")) and os.path.isfile(os.path.join(pk, "HTML", "katex", "katex.min.js"))
                    and os.path.isdir(os.path.join(pk, "HTML", "img")), "exit %s %s" % (code3, out3[-120:])))
        code4, out4 = sh("package_output.py", c, "--dest", "C:/Users/x/Horus University In Egypt/out")
        res.append(("package_output: refuses a destination inside the Teams sync folder", code4 == 1 and "Teams sync folder" in out4, "exit %s" % code4))
        edit_json(lp, lambda d: d["modules"][0]["problems"][0].update({"page_or_slide": 99}))
        code, out = sh("build_capsule.py", c)
        res.append(("build_capsule: page outside the PDF -> fails", code == 1 and "outside" in out, "exit %s" % code))
    os.remove(os.path.join(c, "_audit", "spot_check.json"))
    code, out = sh("build_capsule.py", c)
    res.append(("build_capsule: blocked when validate fails", code == 1 and "BLOCKED" in out, "exit %s" % code))
    code, out = sh("backtest.py", c)
    res.append(("backtest: no past exams -> skips, exit 0", code == 0 and "not calibrated" in out, "exit %s" % code))
    edit_json(os.path.join(c, "course.json"), lambda d: d.update({"calibration": "past_exams"}))
    code, out = sh("backtest.py", c)
    res.append(("backtest: exams but no appeared_in -> fails with fix", code == 1 and "appeared_in" in out, "exit %s" % code))
    edit_json(lp, lambda d: d["modules"][0]["problems"][0].update({"appeared_in": ["Midterm_2025"], "recurrence_sources": ["Midterm_2025", "b"]}))
    code, out = sh("backtest.py", c)
    bt = json.load(open(os.path.join(c, "_audit", "backtest.json"), encoding="utf-8"))
    res.append(("backtest: computes hit rate", code == 0 and bt.get("calibrated") and bt["exams"]["Midterm_2025"]["k"] == 1, out.strip()[-80:]))
    r = subprocess.run([sys.executable, os.path.join(S, "build_master.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    res.append(("build_master: usage error without a course", r.returncode == 2, "exit %s" % r.returncode))
    # draft_ledger + verify_kit
    try:
        import fitz as _f
        import sympy  # noqa: F401
        dd = _f.open()
        pg = dd.new_page()
        pg.insert_text((50, 80), "[1] A wall of thickness L = 0.3 m and k = 0.69 W/m.C is at 20 C. Determine the heat rate.")
        pg.insert_text((50, 160), "[2] A plate of area A = 2 m2. (a) Find the flux. (b) Find the power.")
        sp_ = os.path.join(tmp, "mini_sheet.pdf")
        dd.save(sp_)
        dd.close()
        cdir = os.path.join(tmp, "dl")
        os.makedirs(cdir)
        r1 = subprocess.run([sys.executable, os.path.join(S, "draft_ledger.py"), cdir, sp_, "--label", "Sheet 1"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        dr = json.load(open(os.path.join(cdir, "_audit", "ledger_draft.json"), encoding="utf-8")) if r1.returncode == 0 else []
        res.append(("draft_ledger: splits problems, drafts source_ref, givens and asks",
                    len(dr) == 2 and dr[0]["source_ref"] == "Sheet 1 · Q1" and any("0.3" in g for g in dr[0]["givens_tex"]) and len(dr[1]["parts"]) == 2,
                    "exit %s n=%d" % (r1.returncode, len(dr))))
        kit_script = os.path.join(tmp, "kit_demo.py")
        with open(kit_script, "w", encoding="utf-8") as kf:
            kf.write("import sys\n")
            kf.write("sys.path.insert(0, %r)\n" % S)
            kf.write("from verify_kit import Kit, symbols, pi\n")
            kf.write("K = Kit(%r)\n" % cdir)
            kf.write("p = K.problem('P1')\n")
            kf.write("A, D, Q, L, k, dT = symbols('A D Q L k DeltaT')\n")
            kf.write("p.calc(A, pi*D**2/4, {D: 0.2}, unit=r'\\text{m}^2')\n")
            kf.write("p.calc(dT, Q*L/(k*A), {Q: 800, L: 0.004, k: 237})\n")
            kf.write("p.expect(dT, 0.43, rel_tol=0.01, source='x')\n")
            kf.write("sys.exit(0 if K.save() else 1)\n")
        r2 = subprocess.run([sys.executable, kit_script], capture_output=True, text=True, encoding="utf-8", errors="replace")
        stp = json.load(open(os.path.join(cdir, "_verify", "steps.json"), encoding="utf-8")) if r2.returncode == 0 else {}
        res.append(("verify_kit: SymPy check passes and writes the LaTeX line (frac, numbers, value)",
                    r2.returncode == 0 and len(stp.get("P1", [])) == 2 and "frac" in stp["P1"][1], (r2.stdout + r2.stderr)[-150:]))
    except ImportError:
        pass
    r = subprocess.run([sys.executable, os.path.join(S, "ocr_sources.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    res.append(("ocr_sources: usage error without a course", r.returncode == 2, "exit %s" % r.returncode))
    return res


def main():
    tmp = tempfile.mkdtemp(prefix="hue_v4_test_")
    problems = []
    try:
        for name, ok, detail in preflight_tests(tmp):
            print("%-52s -> %s" % (name, "ok" if ok else "FAILED (%s)" % detail))
            if not ok:
                problems.append("%s: %s" % (name, detail))
        for name, ok, detail in tool_tests(tmp):
            print("%-52s -> %s" % (name, "ok" if ok else "FAILED (%s)" % detail))
            if not ok:
                problems.append("%s: %s" % (name, detail))
        good = make_good(os.path.join(tmp, "good"))
        code, out = run(good)
        print("good fixture ->", "PASS" if code == 0 else "FAIL (unexpected)")
        if code != 0:
            problems.append("good fixture failed:\n" + out)
        for fn in BAD:
            c = make_good(os.path.join(tmp, fn.__name__))
            fn(c)
            code, out = run(c)
            ok = code == 1
            print("%-36s -> %s" % (fn.__name__, "correctly rejected" if ok else "WRONGLY PASSED"))
            if not ok:
                problems.append("%s was not rejected:\n%s" % (fn.__name__, out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if problems:
        print("\nSELF-TEST FAILED")
        for p in problems:
            print(p)
        return 1
    print("\nSELF-TEST PASSED: gatekeeper accepts the good course and rejects all %d broken ones" % len(BAD) + "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
