"""Master gatekeeper. Usage: python validate.py <course_dir> [--post-build]

Runs every gate in order, writes capsule_state.json, prints the acceptance report generated from real
results, and exits 1 if ANY gate fails. There is no warning-only path.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gates  # noqa: E402


def main(argv):
    if not argv:
        print("usage: validate.py <course_dir> [--post-build]")
        return 2
    course = argv[0]
    post = "--post-build" in argv
    cpath = os.path.join(course, "course.json")
    if not os.path.isfile(cpath):
        print("FAIL: course.json missing in %s" % course)
        return 1
    cfg = gates.jload(cpath)
    plan = list(gates.GATES)
    if post:
        plan.append(("freshness", gates.gate_freshness))
    state = {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "gates": {}}
    failed = False
    for name, fn in plan:
        try:
            ok, msgs, ev = fn(course, cfg)
        except Exception as exc:  # a crashing gate is a failing gate
            ok, msgs, ev = False, ["gate crashed: %r" % exc], {}
        state["gates"][name] = {"ok": ok, "messages": msgs, "evidence": ev}
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
        for m in msgs[:12]:
            print("    - " + m)
        if len(msgs) > 12:
            print("    ... %d more" % (len(msgs) - 12))
        failed = failed or not ok
    with open(os.path.join(course, "capsule_state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print("\nACCEPTANCE (generated from gate results, not written by the agent):")
    for name, g in state["gates"].items():
        print("  [%s] %s" % ("x" if g["ok"] else " ", name))
    print("RESULT: %s" % ("FAILED - do not build or claim done" if failed else "ALL GATES PASSED"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
