"""Preflight: discover what the skill needs, and ask the user ONLY about what is missing.

Usage:
  python preflight.py <course_dir> [--answer key=value ...] [--speed] [--no-env]

Exit codes: 0 = all good (no questions), 3 = needs user input (questions in the JSON), 1 = blocked by the
environment (tool/module/key missing; the JSON says exactly what to fix).

Rules: never ask for something that can be discovered; at most 3 questions per round, blocking first;
--speed asks blocking items only; answers are saved into course.json so nothing is asked twice;
API keys are checked by variable NAME only and never printed.
"""
import copy
import importlib.util
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gates  # noqa: E402

MEDIA_EXT = (".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".wav")
DOC_EXT = (".pdf", ".pptx", ".docx")
QBANK_RE = re.compile(r"(question|bank|sheet|summary|mcq|exercise|problem)", re.I)
CALIB_RE = re.compile(r"(exam|quiz|midterm|final|past|previous|model.?answer)", re.I)
MAX_QUESTIONS = 3


def _walk(root, exts):
    out = []
    for base, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith(exts):
                out.append(os.path.join(base, f))
    return sorted(out)


def _stem_name(path):
    return re.sub(r"[^\w]+", "_", os.path.splitext(os.path.basename(path))[0]).strip("_")


def discover_roots(cfg):
    # An explicit list (even an empty one) wins; only a missing key falls back to the default Teams location.
    roots = cfg["discover_roots"] if "discover_roots" in cfg else [os.path.join(os.path.expanduser("~"), "Horus University In Egypt")]
    name_tokens = [t for t in gates.norm(cfg.get("course_name", "")).split() if len(t) > 2]
    code = gates.norm(cfg.get("course_code", ""))
    found = []
    for r in roots:
        if not os.path.isdir(r):
            continue
        for d in sorted(os.listdir(r)):
            full = os.path.join(r, d)
            if not os.path.isdir(full):
                continue
            n = gates.norm(d)
            if (name_tokens and all(t in n for t in name_tokens)) or (not name_tokens and code and code in n):
                found.append(full)
    return found


def _item(id_, kind, status, detail="", candidates=None):
    d = {"id": id_, "kind": kind, "status": status, "detail": detail}
    if candidates:
        d["candidates"] = candidates
    return d


def run(course, cfg, write=False, check_env=True, speed=False):
    """Evaluate requirements. Never mutates the caller's cfg; returns (result_dict, new_cfg)."""
    cfg = copy.deepcopy(cfg)
    items, autofilled = [], []
    skipped = set(cfg.get("skipped", []))

    # --- identity
    if cfg.get("course_code") and cfg.get("course_name"):
        items.append(_item("identity", "blocking", "ok", "%s %s" % (cfg["course_code"], cfg["course_name"])))
    else:
        items.append(_item("identity", "blocking", "missing", "course code/name not set"))

    # --- root
    root = cfg.get("root", "")
    if root and os.path.isdir(root):
        items.append(_item("root", "blocking", "ok", root))
    else:
        cands = discover_roots(cfg) if items[0]["status"] == "ok" else []
        if len(cands) == 1:
            cfg["root"] = root = cands[0]
            autofilled.append("root")
            items.append(_item("root", "blocking", "ok", "auto-detected: %s" % root))
        elif len(cands) > 1:
            items.append(_item("root", "blocking", "ambiguous", "several matching folders", cands))
        else:
            items.append(_item("root", "blocking", "missing", "course folder not found"))

    # --- exam date
    ex = cfg.get("exam", {})
    items.append(_item("exam_date", "blocking", "ok" if ex.get("date") else "missing", ex.get("date", "exam date not set")))

    root_ok = bool(root and os.path.isdir(root))
    # --- media
    if cfg.get("no_recordings"):
        items.append(_item("media", "blocking", "skipped_by_user", "user confirmed: no recordings"))
    elif cfg.get("media") and not root_ok:
        items.append(_item("media", "blocking", "unknown", "cannot verify files until the course folder is known"))
    elif cfg.get("media"):
        miss =[m["video"] for m in cfg["media"] if not os.path.isfile(os.path.join(root, m["video"]))]
        items.append(_item("media", "blocking", "missing" if miss else "ok",
                           ("missing files: %s" % miss) if miss else "%d media files" % len(cfg["media"])))
    elif root_ok:
        files = _walk(root, MEDIA_EXT)
        if files:
            cfg["media"] = [{"video": os.path.relpath(f, root).replace("\\", "/"),
                             "audio": "_audio/%s.mp3" % _stem_name(f),
                             "transcript": "_audio/%s_transcript.txt" % _stem_name(f)} for f in files]
            autofilled.append("media")
            items.append(_item("media", "blocking", "ok", "auto-detected %d recordings" % len(files)))
        else:
            items.append(_item("media", "blocking", "missing", "no recordings found under the course folder"))
    else:
        items.append(_item("media", "blocking", "unknown", "cannot search until the course folder is known"))

    # --- documents (quality) and calibration (recommended)
    docs = _walk(root, DOC_EXT) if root_ok else []
    slides = [d for d in docs if not QBANK_RE.search(os.path.basename(d)) and not CALIB_RE.search(os.path.basename(d))]
    qbank = [d for d in docs if QBANK_RE.search(os.path.basename(d))]
    calib = [d for d in docs if CALIB_RE.search(os.path.basename(d))]

    def doc_item(id_, found, kind):
        if id_ in skipped:
            return _item(id_, kind, "skipped_by_user", "user confirmed: none")
        if found:
            return _item(id_, kind, "ok", "%d files" % len(found))
        if not root_ok:
            return _item(id_, kind, "unknown", "cannot search until the course folder is known")
        return _item(id_, kind, "missing", "no matching files found")

    items.append(doc_item("slides", slides, "quality"))
    items.append(doc_item("question_bank", qbank, "quality"))
    if cfg.get("calibration") == "none":
        items.append(_item("calibration", "recommended", "skipped_by_user", "no past exams/quizzes (capsule will say: not calibrated)"))
    elif cfg.get("calibration") and os.path.exists(str(cfg["calibration"])):
        items.append(_item("calibration", "recommended", "ok", str(cfg["calibration"])))
    else:
        items.append(doc_item("calibration", calib, "recommended"))

    # --- glossary: the agent builds it from the slides, so it is a todo, never a user question
    gl = cfg.get("glossary", "glossary.txt")
    items.append(_item("glossary", "agent_todo", "ok" if os.path.isfile(os.path.join(course, gl)) else "todo",
                       "agent builds glossary.txt from the slides"))

    # --- environment (names only for secrets)
    if check_env:
        env = []
        if not shutil.which("ffmpeg"):
            env.append(_item("ffmpeg", "environment", "blocked", "ffmpeg not on PATH. Install: winget install Gyan.FFmpeg"))
        if not importlib.util.find_spec("fitz"):
            env.append(_item("pymupdf", "environment", "blocked", "Python module missing. Install: pip install pymupdf"))
        has_key = bool(os.environ.get("GROQ_API_KEY")) and bool(importlib.util.find_spec("openai"))
        has_local = bool(importlib.util.find_spec("faster_whisper"))
        if not (has_key or has_local):
            env.append(_item("transcription", "environment", "blocked",
                             "no transcription path: set the GROQ_API_KEY environment variable (and pip install openai) or pip install faster-whisper"))
        free_gb = shutil.disk_usage(course if os.path.isdir(course) else os.path.dirname(os.path.abspath(course)) or ".").free / 1e9
        if free_gb < 2:
            env.append(_item("disk", "environment", "blocked", "less than 2 GB free"))
        items += env or [_item("environment", "environment", "ok", "ffmpeg, pymupdf, transcription path, disk")]

    # --- questions
    order = {"blocking": 0, "quality": 1, "recommended": 2}
    ask = [i for i in items if i["status"] in ("missing", "ambiguous") and i["kind"] in order]
    if speed:
        ask = [i for i in ask if i["kind"] == "blocking"]
    ask.sort(key=lambda i: order[i["kind"]])
    questions = [_question(i) for i in ask]
    deferred = [q["id"] for q in questions[MAX_QUESTIONS:]]
    questions = questions[:MAX_QUESTIONS]

    blocked = [i for i in items if i["status"] == "blocked"]
    status = "blocked" if blocked else ("needs_input" if questions or deferred else "ok")
    result = {"status": status, "items": items, "questions": questions, "deferred_questions": deferred,
              "autofilled": autofilled}
    return result, cfg


def _question(item):
    i, c = item["id"], item.get("candidates", [])
    q = {"id": i, "kind": item["kind"], "found": item["detail"]}
    if i == "identity":
        q.update(text_ar="محتاج أعرف كود المادة واسمها (والدكتور لو تحب).", answer_format="course_code=...,course_name=...,instructor=...")
    elif i == "root" and c:
        q.update(text_ar="لقيت أكتر من مجلد ممكن يكون للمادة. أنهي واحد؟",
                 options=[{"n": k + 1, "answer": "root=%s" % p, "label": p} for k, p in enumerate(c)])
    elif i == "root":
        q.update(text_ar="ملقيتش مجلد المادة على جهازك. اكتب مساره الكامل.", answer_format="root=<path>")
    elif i == "exam_date":
        q.update(text_ar="إمتى الامتحان؟ (التاريخ، والوقت والقاعة لو تعرفهم)", answer_format="exam_date=YYYY-MM-DD,exam_time=...,hall=...")
    elif i == "media":
        q.update(text_ar="ملقيتش تسجيلات للمحاضرات أو السكاشن. تكمل بالشرائح والملفات بس؟",
                 options=[{"n": 1, "answer": "no_recordings=true", "label": "no_recordings=true", "default": True},
                          {"n": 2, "answer": "root=<path>", "label": "root=<path to another folder>"}])
    elif i in ("slides", "question_bank"):
        q.update(text_ar="ملقيتش ملفات لـ %s. تكمل من غيرها؟" % ("الشرائح" if i == "slides" else "بنك الأسئلة"),
                 options=[{"n": 1, "answer": "skip=%s" % i, "label": "skip=%s" % i, "default": True},
                          {"n": 2, "answer": "root=<path>", "label": "root=<path where the files are>"}])
    elif i == "calibration":
        q.update(text_ar="عندك امتحانات سابقة أو كويزات للدكتور؟ لو ملقتش، التوقع هيتكتب إنه غير معايَر.",
                 options=[{"n": 1, "answer": "calibration=none", "label": "calibration=none", "default": True},
                          {"n": 2, "answer": "calibration=<path>", "label": "calibration=<path to folder or file>"}])
    return q


def apply_answer(cfg, pair):
    if "=" not in pair:
        raise ValueError("answer must look like key=value: %r" % pair)
    k, v = pair.split("=", 1)
    k, v = k.strip(), v.strip()
    if k == "skip":
        cfg.setdefault("skipped", [])
        for s in v.split(","):
            if s and s not in cfg["skipped"]:
                cfg["skipped"].append(s)
    elif k in ("exam_date", "exam_time", "hall"):
        cfg.setdefault("exam", {})[{"exam_date": "date", "exam_time": "time", "hall": "hall"}[k]] = v
    elif k == "no_recordings":
        cfg["no_recordings"] = v.lower() in ("1", "true", "yes")
    elif k in ("root", "course_code", "course_name", "instructor", "calibration"):
        cfg[k] = v
    else:
        raise ValueError("unknown answer key: %s" % k)


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Arabic questions must not depend on the console code page
    if not argv:
        print(__doc__)
        return 2
    course = argv[0]
    answers, i = [], 1
    while i < len(argv):
        if argv[i] == "--answer":
            answers.append(argv[i + 1])
            i += 2
        else:
            i += 1
    os.makedirs(course, exist_ok=True)
    cpath = os.path.join(course, "course.json")
    cfg = gates.jload(cpath) if os.path.isfile(cpath) else {}
    # answers like "course_code=X,course_name=Y" may be comma-joined
    for a in answers:
        for part in re.split(r",(?=\w+=)", a):
            apply_answer(cfg, part)
    result, new_cfg = run(course, cfg, write=True, check_env="--no-env" not in argv, speed="--speed" in argv)
    with open(cpath, "w", encoding="utf-8") as f:
        json.dump(new_cfg, f, ensure_ascii=False, indent=2)
    os.makedirs(os.path.join(course, "_audit"), exist_ok=True)
    with open(os.path.join(course, "_audit", "preflight.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {"ok": 0, "needs_input": 3, "blocked": 1}[result["status"]]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
