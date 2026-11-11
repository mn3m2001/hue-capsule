"""Candidate finder for stage 6. Usage: python draft_evidence.py <course_dir>

Scans every transcript line for exam-signal phrases (Arabic + English) and writes _audit/evidence_candidates.json:
media, t_start, t_end, the VERBATIM transcript line as `quote`, and a suggested type. It writes NO evidence: the
model/human picks, edits claim/speaker, and copies chosen items to evidence.jsonl (the evidence gate then checks them).
"""
import json
import os
import re
import sys

SIGNALS = [  # (regex, suggested type)
    (r"مش مطلوب|مش هييجي|مش هيجي|مش داخل|ملهاش دعوة|not required|will not (come|be)|not in the exam", "exclusion"),
    (r"هييجي|هيجي|جاي في الامتحان|هتيجي|سؤال نظري|in the exam|will come|appears? in", "promise"),
    (r"احفظ|حافظ|محتاج أكون حافظ|لازم تعرف|يجب أن أعرف|مهم|الجزء المهم|memorize|important|must know|remember", "emphasis"),
    (r"غلط|خد بالك|فخ|انتبه|careful|trap|mistake|common error", "trap"),
    (r"نحل|نشوف المسائل|مسألة|سؤال على|عايزك تحسب|let'?s solve|problem|calculate", "solved_in_class"),
]
LINE = re.compile(r"^\[(\d+(?:\.\d+)?)\s*->\s*(\d+(?:\.\d+)?)\]\s*(.+)$")


def main(argv):
    if not argv:
        print("usage: draft_evidence.py <course_dir>")
        return 2
    course = argv[0]
    cfg = json.load(open(os.path.join(course, "course.json"), encoding="utf-8"))
    out = []
    for m in cfg.get("media", []):
        tp = os.path.join(course, m["transcript"])
        if not os.path.isfile(tp):
            print("missing transcript: %s" % tp)
            return 1
        for raw in open(tp, encoding="utf-8"):
            mm = LINE.match(raw.strip())
            if not mm:
                continue
            a, b, text = float(mm.group(1)), float(mm.group(2)), mm.group(3).strip()
            for rx, typ in SIGNALS:
                if re.search(rx, text, re.I):
                    out.append({"media": m["video"], "t_start": a, "t_end": max(b, a + 1), "quote": text,
                                "suggested_type": typ, "speaker": "UNSET (ta or doctor: decide from the video)"})
                    break
    os.makedirs(os.path.join(course, "_audit"), exist_ok=True)
    with open(os.path.join(course, "_audit", "evidence_candidates.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    by = {}
    for c in out:
        by[c["suggested_type"]] = by.get(c["suggested_type"], 0) + 1
    print("%d candidates -> _audit/evidence_candidates.json %s" % (len(out), by))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
