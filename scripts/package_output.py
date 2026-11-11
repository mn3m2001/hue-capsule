"""Package the finished capsule into its final folder. Usage:

    python package_output.py <course_dir> [--dest <folder>]

Creates  <dest>/<CODE>_<Course_Name>/
             PDF/        the PDF deliverables (1_Master, 2_Formulas, 3_Theory, 4_Questions, plus the _EN versions)
             HTML/       the same pages as HTML, with the img/ and katex/ folders they need (open index by double click)
             _evidence/  evidence.jsonl, ledger, ranking, state and the self-review (for audit)
`--dest` defaults to `output_dir` in course.json, else <course_dir>/output. Rule: never write into the Teams sync folder and
never overwrite the user's older files: only this packaged folder is written. A PDF that is open in a viewer cannot be
overwritten: it is saved next to it as `name_v2.pdf` (and reported).
Refuses to run unless `validate.py --post-build` passes and the four base PDFs exist.
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def safe_copy(src, dst, notes):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        shutil.copyfile(src, dst)
        return dst
    except OSError:
        base, ext = os.path.splitext(dst)
        n = 2
        while os.path.exists("%s_v%d%s" % (base, n, ext)):
            n += 1
        alt = "%s_v%d%s" % (base, n, ext)
        shutil.copyfile(src, alt)
        notes.append("locked (open in a viewer): %s -> saved as %s" % (os.path.basename(dst), os.path.basename(alt)))
        return alt


def main(argv):
    if not argv or argv[0].startswith("-"):
        print("usage: package_output.py <course_dir> [--dest <folder>]")
        return 2
    course = argv[0]
    r = subprocess.run([sys.executable, os.path.join(HERE, "validate.py"), course, "--post-build"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print("BLOCKED: validate.py --post-build failed, nothing packaged.\n" + r.stdout[-1200:])
        return 1
    with open(os.path.join(course, "course.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    code = cfg.get("course_code", "COURSE")
    nice = re.sub(r"[^A-Za-z0-9]+", "_", str(cfg.get("course_name", ""))).strip("_")
    dest = argv[argv.index("--dest") + 1] if "--dest" in argv else cfg.get("output_dir") or os.path.join(course, "output")
    if "Horus University In Egypt" in dest.replace("\\", "/"):
        print("BLOCKED: %s is inside the Teams sync folder (it uploads to the class SharePoint). Choose another --dest." % dest)
        return 1
    build = os.path.join(course, "build")
    sys.path.insert(0, HERE)
    import style as st
    base = [st.fname(cfg, "master", "ar") + ".pdf", st.fname(cfg, "formulas") + ".pdf", st.fname(cfg, "theory") + ".pdf", st.fname(cfg, "questions", "ar") + ".pdf"]
    missing = [b for b in base if not os.path.isfile(os.path.join(build, b))]
    if missing:
        print("FAIL: missing PDFs in build/: %s. Fix: build_capsule.py <course> --pdf --lang both, then build_master.py <course> --lang both" % ", ".join(missing))
        return 1
    root = os.path.join(dest, "%s_%s" % (code, nice) if nice else code)
    notes, n_pdf, n_html = [], 0, 0
    for fn in sorted(os.listdir(build)):
        src = os.path.join(build, fn)
        if os.path.isfile(src) and fn.lower().endswith(".pdf"):
            safe_copy(src, os.path.join(root, "PDF", fn), notes)
            n_pdf += 1
        elif os.path.isfile(src) and fn.lower().endswith(".html"):
            safe_copy(src, os.path.join(root, "HTML", fn), notes)
            n_html += 1
    for sub in ("img", "katex"):
        sd = os.path.join(build, sub)
        if os.path.isdir(sd):
            for dp, _, files in os.walk(sd):
                for fn in files:
                    rel = os.path.relpath(os.path.join(dp, fn), build)
                    safe_copy(os.path.join(dp, fn), os.path.join(root, "HTML", rel), notes)
    for ev in ("evidence.jsonl", "course_curriculum_ledger.json", "ranking.json", "capsule_state.json"):
        if os.path.isfile(os.path.join(course, ev)):
            safe_copy(os.path.join(course, ev), os.path.join(root, "_evidence", ev), notes)
    for vf in ("results.json", "sympy_results.json"):
        vp = os.path.join(course, "_verify", vf)
        if os.path.isfile(vp):
            safe_copy(vp, os.path.join(root, "_evidence", "verify_" + vf), notes)
    if os.path.isfile(os.path.join(course, "term_map.json")):
        safe_copy(os.path.join(course, "term_map.json"), os.path.join(root, "_evidence", "term_map.json"), notes)
    rs = os.path.join(course, "_audit", "review_self.md")
    if os.path.isfile(rs):
        safe_copy(rs, os.path.join(root, "_evidence", "review_self.md"), notes)
    print("packaged: %s\n  PDF/ %d files, HTML/ %d pages (+ img, katex), _evidence/" % (root, n_pdf, n_html))
    for x in notes:
        print("  NOTE: " + x)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
