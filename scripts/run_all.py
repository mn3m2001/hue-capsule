"""One command for the scripted stages. Usage: python run_all.py <course_dir> [--speed]

Order: self-test -> preflight -> validate (pre-build) -> score -> backtest (skips itself when no past exams) -> link review. Stops at the first failure and prints
ONE line saying what to do. Stages that need a model or a human (transcribe, evidence, ledger, SymPy, spot check,
build) are NOT run here: the failing gate tells which one is next.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
FIX = {
    "self-test": "the gatekeeper is broken: stop and tell the user (do not edit scripts/ or tests/)",
    "preflight": "answer the questions it printed (python preflight.py <course> --answer key=value), then re-run",
    "validate": "fix the failing gate shown above (SKILL.md section 1 says which stage produces it), then re-run",
    "score": "the ledger or evidence file is malformed: fix it, then re-run",
    "backtest": "mark which problems appeared in each past exam (appeared_in in the ledger), then re-run",
    "link review": "add `link_basis` to the problem, or fix the evidence_ids (see _audit/link_review.md)",
}


def step(name, cmd):
    print("== %s" % name)
    r = subprocess.run([PY] + cmd)
    if r.returncode not in (0,):
        print("\nSTOPPED at '%s' (exit %d). Next: %s" % (name, r.returncode, FIX[name]))
        sys.exit(1)


def draft_sheets(course):
    """Optional: course.json `problem_sheets` = [{"path": "...pdf", "label": "Sheet 1"}]; drafts ledger problems for each (never blocks)."""
    import json
    try:
        cfg = json.load(open(os.path.join(course, "course.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return
    sheets = cfg.get("problem_sheets") or []
    if not sheets or os.path.isfile(os.path.join(course, "_audit", "ledger_draft.json")):
        return
    print("== ledger draft (problem_sheets)")
    for sh in sheets:
        r = subprocess.run([PY, os.path.join(HERE, "draft_ledger.py"), course, sh["path"], "--label", sh.get("label", "Sheet")])
        if r.returncode != 0:
            print("NOTE: draft failed for %s (scanned PDF? use ocr_sources.py); continuing" % sh["path"])


def main(argv):
    if not argv:
        print("usage: run_all.py <course_dir> [--speed]")
        return 2
    course = argv[0]
    step("self-test", [os.path.join(HERE, "..", "tests", "run_tests.py")])
    step("preflight", [os.path.join(HERE, "preflight.py"), course] + (["--speed"] if "--speed" in argv else []))
    step("validate", [os.path.join(HERE, "validate.py"), course])
    draft_sheets(course)
    step("score", [os.path.join(HERE, "score_topics.py"), course])
    step("backtest", [os.path.join(HERE, "backtest.py"), course])
    step("link review", [os.path.join(HERE, "review_links.py"), course])
    print("\nALL SCRIPTED STAGES PASSED. Next (model/human): review, humanize, build, then validate.py --post-build.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
