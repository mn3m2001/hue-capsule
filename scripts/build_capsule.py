"""Build three of the four deliverables as HTML/PDF (2_Formulas, 3_Theory, 4_Questions; 1_Master comes from build_master.py). Course-agnostic.

Usage: python build_capsule.py <course_dir> [--pdf] [--dpi 110] [--exam N]

The questions file ends with a practice paper (top N non-excluded ranked problems, default 6, `--exam 0` to skip) and its
model answer, labelled with its calibration status from _audit/backtest.json.
Ledger fields required for the detailed files: formulas `symbols_ar` + `when_ar` (+ `tex`); theory items `explain_ar`;
problems `explain_ar`, `solution_tex` (LaTeX lines) with `steps_ar` (one Arabic explanation per line), optional `mistakes_ar`;
modules may carry `tables` ({title_ar, headers_ar, rows_ar}).
`--lang both` also writes 4_Questions_<CODE>_EN (needs `explain_en`, `steps_en`, optional `mistakes_en`).

- Refuses to run unless `validate.py` exits 0 (hard rule: no build before the gates pass).
- Every problem shows the ORIGINAL source page as a PNG (rendered with PyMuPDF) next to the question text,
  evidence quotes and solution steps, so figures, tables and handwriting are never lost.
- Solution steps come from the ledger (`solution_steps`: list of strings). A problem without steps, or whose
  source page cannot be rendered, is a failure (exit 1): nothing is silently skipped.
- Banner text: `banner` in course.json, else `evidence_note` in the ledger (shown on every page).
- Updates `deliverables` in course.json, then you run `validate.py --post-build`.
"""
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import style as st  # noqa: E402

e = html.escape

CSS = ("<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;line-height:1.5}"
       "code,pre{background:#f3f3f3;padding:2px 4px}.warn{border:2px solid #c00;padding:8px;background:#fff0f0}"
       ".card{border:1px solid #bbb;border-radius:6px;padding:10px;margin:12px 0;break-inside:auto}"
       ".q{color:#444;font-size:.9em;margin:4px 0}h1,h2{color:#07575b}"
       ".grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px}"
       ".grid img{width:100%;border:1px solid #999;break-inside:avoid}.src{font-size:.8em;color:#666}"
       "@media(max-width:700px){.grid{grid-template-columns:1fr}}</style>")


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def find_source(name, roots, cache):
    if name in cache:
        return cache[name]
    cache[name] = None
    for r in roots:
        if not r or not os.path.isdir(r):
            continue
        for dp, _, files in os.walk(r):
            if name in files:
                cache[name] = os.path.join(dp, name)
                return cache[name]
    return None


def bc_first(spec):
    return pages_of(spec)[0]


def pages_of(spec):
    """page_or_slide -> list of 1-based pages. Accepts 5, '5', '5-6'."""
    s = str(spec).strip()
    if "-" in s:
        a, b = s.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(s)]


def render(path, page, out_png, dpi, crop=None):
    """Render one PDF page to PNG. crop=(start_text, end_text_or_None): keep only the band from the line that contains
    start_text down to the line that contains end_text (or the bottom of the page content), full width."""
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    try:
        if page < 1 or page > doc.page_count:
            return "page %d outside 1..%d" % (page, doc.page_count)
        pg = doc[page - 1]
        clip = None
        if crop and crop[0]:
            a = pg.search_for(crop[0])
            if not a:
                return "crop_start text not found on page %d: %r" % (page, crop[0])
            y0 = max(a[0].y0 - 7, 0)
            if crop[1]:
                b = [r for r in pg.search_for(crop[1]) if r.y0 > a[0].y0]
                if not b:
                    return "crop_end text not found below the start on page %d: %r" % (page, crop[1])
                y1 = b[0].y0 - 8
            else:
                blocks = [bl for bl in pg.get_text("blocks") if bl[3] > y0 and bl[1] < pg.rect.height * 0.9]
                y1 = min(max([bl[3] for bl in blocks] + [y0 + 40]) + 8, pg.rect.height)
                for im in pg.get_image_info():
                    y1 = max(y1, min(im["bbox"][3] + 4, pg.rect.height))
            clip = fitz.Rect(0, y0, pg.rect.width, max(y1, y0 + 30))
        pg.get_pixmap(dpi=dpi, clip=clip).save(out_png)
    finally:
        doc.close()
    return None


def find_browser():
    for n in ("msedge", "chrome", "google-chrome", "chromium"):
        p = shutil.which(n)
        if p:
            return p
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if os.path.isfile(p):
            return p
    return None


def main(argv):
    if not argv or argv[0].startswith("-"):
        print("usage: build_capsule.py <course_dir> [--pdf] [--dpi N] [--exam N] [--lang ar|en|both]")
        return 2
    course = argv[0]
    dpi = int(argv[argv.index("--dpi") + 1]) if "--dpi" in argv else 110
    r = subprocess.run([sys.executable, os.path.join(HERE, "validate.py"), course], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print("BLOCKED: validate.py failed, no build before the gates pass.\n" + r.stdout[-1500:])
        return 1
    cfg = jload(os.path.join(course, "course.json"))
    ledger = jload(os.path.join(course, "course_curriculum_ledger.json"))
    ev = {}
    with open(os.path.join(course, "evidence.jsonl"), encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                d = json.loads(ln)
                ev[d["id"]] = d
    rkp = os.path.join(course, "ranking.json")
    ranking = jload(rkp) if os.path.isfile(rkp) else []
    checks = {}
    vp = os.path.join(course, "_verify", "results.json")
    if os.path.isfile(vp):
        checks = {c["id"]: c for c in jload(vp)["checks"]}
    banner = cfg.get("banner") or ledger.get("evidence_note") or ""
    code, name = cfg.get("course_code", ""), cfg.get("course_name", "")
    out = os.path.join(course, "build")
    img = os.path.join(out, "img")
    os.makedirs(img, exist_ok=True)
    roots = [cfg.get("root"), course]
    cache, errors = {}, []
    st.lint_terms(course, ledger, ev, errors)

    def page(title, body, subtitle=""):
        b = '<div class="box honest"><span class="ltr">%s</span></div>' % e(banner) if banner else ""
        return st.document(title, st.header(code, name, cfg.get("instructor"), cfg.get("exam", {}).get("date"), subtitle or title) + b + body)

    def quote(i):
        return st.quote_row(ev[i], i)

    def images_for(item_id, src, spec, item=None):
        """Render source page(s); returns html. Records an error instead of skipping."""
        path = find_source(src, roots, cache)
        if not path:
            errors.append("%s: source file %s not found under root" % (item_id, src))
            return '<div class="warn">source page image missing</div>'
        if not path.lower().endswith(".pdf"):
            ext = os.path.splitext(path)[1]
            dst = "%s_%s%s" % (item_id, "src", ext)
            shutil.copyfile(path, os.path.join(img, dst))
            return '<img src="img/%s" alt="%s">' % (e(dst), e(item_id))
        h = ""
        for pg in pages_of(spec):
            fn = "%s_p%d.png" % (item_id, pg)
            crop = (item.get("crop_start"), item.get("crop_end")) if item and pg == bc_first(spec) else None
            err = render(path, pg, os.path.join(img, fn), dpi, crop)
            if err:
                errors.append("%s: %s (%s)" % (item_id, err, src))
                continue
            h += '<img src="img/%s" alt="%s p.%d"><div class="src">%s, page %d</div>' % (e(fn), e(src), pg, e(src), pg)
        return h

    files = {}
    probs = {p["id"]: p for m in ledger["modules"] for p in m.get("problems", [])}
    rk = {r["id"]: r for r in ranking}
    order = [r["id"] for r in ranking if r["id"] in probs] + [i for i in probs if i not in rk]
    mtitle = lambda m: e(m.get("title", m.get("module_id", "")))  # noqa: E731

    # ---------- 2: formulas (law, symbols and units, when it applies and when not, source)
    b = ""
    for m in ledger["modules"]:
        if not m.get("formulas"):
            continue
        b += '<div class="sec">%s</div>' % mtitle(m)
        for f in m["formulas"]:
            for fld in ("symbols_ar", "when_ar"):
                if not f.get(fld):
                    errors.append("%s: formula has no %s in the ledger" % (f["id"], fld))
            extra = ""
            if f.get("source_file") and f.get("page_or_slide"):
                extra = "<div>%s</div>" % images_for(f["id"], f["source_file"], f["page_or_slide"])
            b += ('<div class="card"><div class="body">%s<div class="pre"><b>الرموز والوحدات:</b> %s</div>'
                  '<div class="pre"><b>متى تنطبق ومتى لا:</b> %s</div><small class="ltr">%s</small>%s%s</div></div>') % (
                st.tex_or_text(f.get("tex"), f.get("title", f["id"])), e(f.get("symbols_ar", "")), e(f.get("when_ar", "")),
                e(f.get("source", "")), "".join(quote(i) for i in f.get("evidence_ids", [])), extra)
    files[st.fname(cfg, "formulas") + ".html"] = page("%s Formulas" % code, b, "مجموعة القوانين")

    # ---------- 3: theory (each concept explained, comparison tables, traps)
    b = ""
    for m in ledger["modules"]:
        items, traps, tables = m.get("theory_items", []), m.get("traps", []), m.get("tables", [])
        if not (items or traps or tables):
            continue
        b += '<div class="sec">%s</div>' % mtitle(m)
        for t in items:
            if not t.get("explain_ar"):
                errors.append("%s: theory item has no explain_ar in the ledger" % t["id"])
            b += '<div class="box"><b class="ltr">%s</b><div class="pre">%s</div><small class="ltr">%s</small>%s</div>' % (
                e(t.get("title", t["id"])), e(t.get("explain_ar", "")), e(t["source"]), "".join(quote(i) for i in t.get("evidence_ids", [])))
        for tb in tables:
            b += '<div class="box"><b>%s</b><table><tr>%s</tr>%s</table></div>' % (
                e(tb.get("title_ar", "")), "".join("<th>%s</th>" % e(h) for h in tb["headers_ar"]),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % e(c) for c in row) for row in tb["rows_ar"]))
        for t in traps:
            b += '<div class="box honest"><b>⚠️ فخ:</b> %s%s</div>' % (e(t["text"]), "".join(quote(i) for i in t.get("evidence_ids", [])))
    files[st.fname(cfg, "theory") + ".html"] = page("%s Theory" % code, b, "دليل النظرية")

    for lang in st.langs_of(argv):
        # ---------- 4: the most important questions, every step explained
        b = '<div class="box">مرتبة بقوة الأدلة. النسبة تقدير مش احتمال حقيقي. كل خطوة جنبها شرحها بالعربي.</div>'
        for n, pid in enumerate(order, 1):
            p = probs[pid]
            tex = p.get("solution_tex") or []
            sar = p.get("steps_" + lang) or []
            steps = p.get("solution_steps") or []
            if not (tex or steps):
                errors.append("%s: no solution_tex/solution_steps in ledger" % pid)
            if not p.get("explain_" + lang):
                errors.append("%s: no explain_%s in ledger" % (pid, lang))
            if tex and len(sar) != len(tex):
                errors.append("%s: steps_%s must have one explanation per solution_tex line (%d vs %d)" % (pid, lang, len(sar), len(tex)))
            ok = [c for k, c in checks.items() if k.split("/")[0] == pid]
            tier = rk.get(pid, {}).get("tier", "possible")
            badges = '<span class="b-%s">%s%s</span>' % (tier if tier in st.TIER_AR else "possible", st.TIER_AR.get(tier, tier),
                                                          " — ثقة تقديرية %d%%" % rk[pid].get("pct", 0) if pid in rk else "")
            if ok and all(c.get("ok") for c in ok):
                badges += '<span class="b-ok">اتحسب تاني ✔ (%d)</span>' % len(ok)
            badges += st.where_spans(p, lang, errors)
            left = images_for(pid, p["source_file"], p["page_or_slide"], p)
            right = '<div class="pre"><b>فهم المسألة قبل الحل (Understand first):</b><br>%s</div>' % e(p.get("explain_" + lang, ""))
            right += '<div class="q">المصدر: <span class="t">%s — page/slide %s</span></div>' % (e(p["source_file"]), e(str(p["page_or_slide"])))
            right += "".join(st.quote_row(ev[i], i, lang) for i in p.get("evidence_ids", [])) or '<div class="q">مفيش تسجيل مرتبط بالمسألة دي.</div>'
            sol = st.solution_html(p, lang, True, errors)
            warn = "".join('<div class="warn">%s</div>' % e(x) for x in steps if x.startswith(("WARNING", "NOTE")))
            mist = ('<div class="box honest"><b>أخطاء شائعة (Common mistakes):</b><ul>%s</ul></div>' % "".join("<li>%s</li>" % e(x) for x in p["mistakes_" + lang])
                    if p.get("mistakes_" + lang) else "")
            b += ('<div class="card"><div class="top">Problem %d — %s</div><div class="body"><div class="badges">%s</div>'
                  '<div class="grid"><div>%s</div><div>%s</div></div><div class="sol">%s</div>%s%s</div></div>'
                  ) % (n, e(p.get("title", pid)), badges, left, right, sol, warn, mist)

        # practice paper + model answer, appended to the questions file
        nexam = int(argv[argv.index("--exam") + 1]) if "--exam" in argv else 6
        if nexam:
            pick = [i for i in order if rk.get(i, {}).get("tier") != "excluded"][:nexam]
            bt = os.path.join(course, "_audit", "backtest.json")
            cal = jload(bt) if os.path.isfile(bt) else {"calibrated": False}
            if cal.get("calibrated"):
                note = "معايرة على امتحانات قديمة: " + "؛ ".join("%s نسبة الإصابة %s" % (k, v["hit_rate_confirmed_likely"]) for k, v in cal["exams"].items())
            else:
                note = "الترتيب غير معاير (مفيش امتحانات قديمة): ده ترتيب احتمالات مش ضمان."
            b += '<div class="sec pb">ورقة تدريب (الامتحان المتوقع)</div><div class="box honest">%s<br>ملحوظة: صورة المصدر ممكن تكون فيها خطوات الحل أصلاً.</div>' % e(note)
            for k, pid in enumerate(pick, 1):
                p = probs[pid]
                b += ('<div class="card"><div class="top">Question %d</div><div class="body"><div class="grid"><div>%s</div>'
                      '<div><p class="ltr">%s</p></div></div></div></div>') % (
                    k, images_for("EXAM-" + pid, p["source_file"], p["page_or_slide"], p), e(p.get("title", pid)))
            b += '<div class="sec pb">الإجابة النموذجية</div>'
            for k, pid in enumerate(pick, 1):
                p = probs[pid]
                lines = ("".join('<div class="tex">%s</div>' % e(x) for x in p["solution_tex"]) if p.get("solution_tex")
                         else "".join("<div>%s</div>" % e(x) for x in p.get("solution_steps", []) if not x.startswith(("WARNING", "NOTE"))))
                b += '<div class="card"><div class="top">Answer %d (%s)</div><div class="body"><div class="sol">%s</div></div></div>' % (k, e(pid), lines)
        pg_html = page("%s Key questions" % code, b, "أهم الأسئلة مشروحة بالتفصيل")
        files[st.fname(cfg, "questions", lang) + ".html"] = st.to_en(pg_html) if lang == "en" else pg_html

    if errors:
        print("BUILD FAILED (nothing written to course.json):")
        for x in errors:
            print("  - " + x)
        return 1
    st.copy_katex(out)
    for fn, content in files.items():
        with open(os.path.join(out, fn), "w", encoding="utf-8") as f:
            f.write(content)
    delivs = ["build/" + fn for fn in files]
    if "--pdf" in argv:
        br = find_browser()
        if not br:
            print("NOTE: no Edge/Chrome found, PDF skipped; HTML files are complete")
        else:
            for fn in files:
                src = os.path.abspath(os.path.join(out, fn))
                dst = src[:-5] + ".pdf"
                if os.path.isfile(dst):
                    os.remove(dst)
                prof = tempfile.mkdtemp(prefix="hc_edge_")
                subprocess.run([br, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=8000", "--user-data-dir=" + prof,
                                "--print-to-pdf=" + dst, "file:///" + src.replace(os.sep, "/")],
                               capture_output=True, timeout=120)
                for _ in range(60):  # the browser may return before the file is written
                    if os.path.isfile(dst) and os.path.getsize(dst) > 0:
                        break
                    time.sleep(0.5)
                shutil.rmtree(prof, ignore_errors=True)
                if os.path.isfile(dst):
                    delivs.append("build/" + os.path.basename(dst))
                else:
                    print("NOTE: PDF failed for " + fn)
    cfg["deliverables"] = delivs
    with open(os.path.join(course, "course.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("built %d files in %s; now run: validate.py %s --post-build" % (len(delivs), out, course))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
