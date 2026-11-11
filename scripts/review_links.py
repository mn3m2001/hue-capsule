"""Link review (problem -> evidence). Usage: python review_links.py <course_dir>

The ledger gate only checks that an evidence id EXISTS. This script prints every link (problem title next to the
evidence claim and quote) to _audit/link_review.md and fails (exit 1) for a link with no shared keyword between the
problem and the evidence claim UNLESS the problem carries a written `link_basis` explaining why it applies.
"""
import json
import os
import re
import sys

STOP = {"the", "and", "for", "with", "from", "that", "this", "are", "ta", "solves", "problem", "find", "asks", "asking",
        "calculate", "question"}


def toks(s):
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) >= 3 and t not in STOP}


def main(argv):
    course = argv[0]
    ledger = json.load(open(os.path.join(course, "course_curriculum_ledger.json"), encoding="utf-8"))
    ev = {}
    for line in open(os.path.join(course, "evidence.jsonl"), encoding="utf-8"):
        if line.strip():
            d = json.loads(line)
            ev[d["id"]] = d
    md, bad = ["# Link review\n"], []
    for mod in ledger.get("modules", []):
        for p in mod.get("problems", []):
            for eid in p.get("evidence_ids", []):
                e = ev.get(eid)
                if not e:
                    continue
                shared = toks(p.get("title", "")) & toks(e["claim"])
                md.append("- %s <- %s [%s, %s] shared=%s\n    problem: %s\n    claim: %s\n    quote: %s\n    basis: %s\n" % (
                    p["id"], eid, e["type"], e["speaker"], sorted(shared) or "NONE", p.get("title"), e["claim"],
                    e["quote"], p.get("link_basis", "-")))
                if not shared and not p.get("link_basis"):
                    bad.append("%s <- %s: no shared keyword and no link_basis" % (p["id"], eid))
    os.makedirs(os.path.join(course, "_audit"), exist_ok=True)
    open(os.path.join(course, "_audit", "link_review.md"), "w", encoding="utf-8").write("\n".join(md))
    for b in bad:
        print("WEAK LINK:", b)
    print("link review: %d weak link(s); table in _audit/link_review.md" % len(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
