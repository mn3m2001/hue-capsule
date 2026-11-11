"""Backtest the scoring on past exams, if any exist. Usage: python backtest.py <course_dir>

- No past exams (course.json calibration is missing or "none"): prints "not calibrated", writes
  _audit/backtest.json {"calibrated": false}, exits 0. The run continues normally with the resources it has.
- Past exams exist: ledger items that appeared in an exam carry `appeared_in: ["<exam name>"]` (the model sets it
  at stage 7 after reading the exam). For each exam the scoring is re-run WITHOUT that exam (its name is dropped
  from recurrence_sources) and compared with what really appeared:
    hit rate = appeared items ranked confirmed/likely / appeared items;  top-k = appeared items inside the top k
    (k = number of appeared items).
  Writes _audit/backtest.json and prints the numbers. If exams exist but no item has `appeared_in`, exit 1 with
  the one-line fix (mapping is missing, not a gate being weak).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_topics  # noqa: E402


def main(argv):
    if not argv:
        print("usage: backtest.py <course_dir>")
        return 2
    course = argv[0]
    out = os.path.join(course, "_audit", "backtest.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cfg = json.load(open(os.path.join(course, "course.json"), encoding="utf-8"))
    calib = cfg.get("calibration")
    if not calib or calib == "none":
        json.dump({"calibrated": False, "reason": "no past exams or quizzes"}, open(out, "w", encoding="utf-8"))
        print("backtest skipped: no past exams, the capsule must say 'not calibrated'. Continuing normally.")
        return 0
    ledger = json.load(open(os.path.join(course, "course_curriculum_ledger.json"), encoding="utf-8"))
    items = [p for m in ledger.get("modules", []) for p in m.get("problems", [])]
    exams = sorted({x for p in items for x in p.get("appeared_in", [])})
    if not exams:
        print("FAIL: past exams exist (%s) but no ledger item has appeared_in. Fix: read each past exam and add "
              "appeared_in: [\"<exam name>\"] to the problems it contained, then re-run" % calib)
        return 1
    result = {"calibrated": True, "exams": {}}
    for ex in exams:
        ranking = score_topics.score(course, drop_sources=(ex,), quiet=True)
        order = [r["id"] for r in ranking]
        tier = {r["id"]: r["tier"] for r in ranking}
        appeared = [p["id"] for p in items if ex in p.get("appeared_in", [])]
        k = len(appeared)
        hits = [i for i in appeared if tier[i] in ("confirmed", "likely")]
        topk = [i for i in appeared if order.index(i) < k]
        result["exams"][ex] = {"appeared": k, "hit_rate_confirmed_likely": round(len(hits) / k, 2),
                               "top_k_hits": len(topk), "k": k}
        print("%s: %d/%d appeared items ranked confirmed/likely (%.0f%%); %d/%d inside top %d" % (
            ex, len(hits), k, 100.0 * len(hits) / k, len(topk), k, k))
    json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
