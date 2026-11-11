"""Exam-prediction scoring. Usage: python score_topics.py <course_dir>

Reads course_curriculum_ledger.json + evidence.jsonl, writes ranking.json with a score, a tier
(confirmed / likely / possible) and the reasons for each problem. Weights live in references/scoring.json.
A problem whose evidence says the instructor EXCLUDED it is pushed to the bottom with the reason shown.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def score(course, drop_sources=(), quiet=False):
    """Returns the ranking list. drop_sources: recurrence sources to ignore (used by backtest to avoid leakage)."""
    with open(os.path.join(HERE, "..", "references", "scoring.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    w, tiers = cfg["weights"], cfg["tiers"]
    with open(os.path.join(course, "course_curriculum_ledger.json"), encoding="utf-8") as f:
        ledger = json.load(f)
    ev = {}
    with open(os.path.join(course, "evidence.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                ev[d["id"]] = d
    cpath = os.path.join(course, "course.json")
    if os.path.isfile(cpath):  # per-course override: {"scoring_overrides": {"weights": {...}, "tiers": {...}}}
        ov = json.load(open(cpath, encoding="utf-8")).get("scoring_overrides", {})
        w.update(ov.get("weights", {}))
        tiers.update(ov.get("tiers", {}))
    allp = [p for m in ledger.get("modules", []) for p in m.get("problems", [])]
    bank_flat = bool(allp) and all(p.get("in_question_bank") for p in allp)  # same bonus for all = no information
    if bank_flat and not quiet:
        print("note: every problem is in_question_bank, so that bonus is skipped (it does not discriminate)")
    ranking = []
    for mod in ledger.get("modules", []):
        for p in mod.get("problems", []):
            score, why = 0.0, []
            for eid in p.get("evidence_ids", []):
                e = ev.get(eid)
                if not e:
                    continue
                base = w.get(e["type"], 0.0)
                if e["type"] != "exclusion" and e["speaker"] == "ta":
                    base *= w["ta_speaker_factor"]
                score += base
                why.append("%s by %s (%s)" % (e["type"], e["speaker"], eid))
            extra = max(0, len([x for x in p.get("recurrence_sources", []) if x not in drop_sources]) - 1)
            rec = min(extra * w["recurrence_per_extra_source"], w["recurrence_cap"])
            if rec:
                score += rec
                why.append("appears in %d sources" % (extra + 1))
            if p.get("in_question_bank") and not bank_flat:
                score += w["in_question_bank"]
                why.append("in official question bank")
            tier = "confirmed" if score >= tiers["confirmed"] else "likely" if score >= tiers["likely"] else "possible"
            if any(ev.get(e, {}).get("type") == "exclusion" for e in p.get("evidence_ids", [])):
                tier = "excluded"
            # estimated confidence 0-100: logistic of the evidence score, centred on the "likely" threshold. It ranks
            # evidence strength; it is NOT a calibrated probability (no past exams), and the reports must say so.
            pct = 0 if tier == "excluded" else int(round(100.0 / (1.0 + math.exp(-(score - tiers["likely"]) / 2.0))))
            ranking.append({"id": p["id"], "title": p.get("title"), "score": round(score, 2), "pct": pct, "tier": tier, "why": why})
    ranking.sort(key=lambda r: -r["score"])
    return ranking


def main(argv):
    course = argv[0]
    ranking = score(course)
    with open(os.path.join(course, "ranking.json"), "w", encoding="utf-8") as f:
        json.dump(ranking, f, ensure_ascii=False, indent=2)
    for r in ranking[:15]:
        print("%6.2f  %-9s %s %s" % (r["score"], r["tier"], r["id"], r["title"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
