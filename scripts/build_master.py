"""Build ONE combined master PDF (Arabic, RTL, A4) from the validated course data. Course-agnostic.

Usage: python build_master.py <course_dir> [--dpi 110] [--exam N]

Layout (modelled on the Zaytouna master files):
  cover block (university, course, instructor, honesty box)
  1. What the doctor / TA said: exclusions first, then promises, emphasis, traps, solved in class (recording + time + verbatim quote)
  2. Problems ranked by priority: badge row, source page image, "understand before solving" box, solution steps, spoken evidence, flagged conflicts
  3. Formula compendium
  4. Theory, classifications and traps
  5. Practice paper from the top N ranked problems (questions only; answers are in section 2)
Math: ledger problems may carry `solution_tex` (list of LaTeX lines) and formulas `tex`; they are typeset with the KaTeX copy in assets/katex (offline, copied next to the HTML). Without `solution_tex` the plain `solution_steps` are shown.
Refuses to run unless validate.py exits 0. Source images are cropped to the problem when the ledger problem has `crop_start` (text of its first line) and `crop_end` (first line of the next problem, optional); otherwise the whole page is shown.
Every problem needs `solution_steps` AND `explain_ar` (Egyptian Arabic, 2-4 lines:
what is asked, which law, the usual trap); a missing field or source page is a failure (exit 1). Evidence rows may carry `claim_ar`.
`--lang both` builds the Arabic file and an English one (`_EN`; needs `explain_en` on every problem; evidence `claim` is the English text).
Output: build/1_Master_<COURSE_CODE>.html and .pdf (page numbers stamped as "n / N"); updates course.json deliverables.
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
import build_capsule as bc  # noqa: E402

e = html.escape
from style import (CSS, KATEX, TYPE_AR, TYPE_ORDER, SPK_AR, TIER_AR, mmss, quote_row as _qr, copy_katex, to_en, langs_of, solution_html, where_spans, lint_terms, fname as st_fname)  # noqa: E402


def main(argv):
    if not argv or argv[0].startswith("-"):
        print("usage: build_master.py <course_dir> [--dpi N] [--exam N] [--lang ar|en|both]")
        return 2
    langs = langs_of(argv)
    if len(langs) > 1:
        rest = [a for i, a in enumerate(argv) if a != "--lang" and (i == 0 or argv[i - 1] != "--lang")]
        return max(main(rest + ["--lang", x]) for x in langs)
    lang = langs[0]
    sfx = "_EN" if lang == "en" else ""
    course = argv[0]
    dpi = int(argv[argv.index("--dpi") + 1]) if "--dpi" in argv else 110
    nexam = int(argv[argv.index("--exam") + 1]) if "--exam" in argv else 6
    r = subprocess.run([sys.executable, os.path.join(HERE, "validate.py"), course], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print("BLOCKED: validate.py failed, no build before the gates pass.\n" + r.stdout[-1500:])
        return 1
    jl = bc.jload
    cfg = jl(os.path.join(course, "course.json"))
    ledger = jl(os.path.join(course, "course_curriculum_ledger.json"))
    ev = {}
    with open(os.path.join(course, "evidence.jsonl"), encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                d = json.loads(ln)
                ev[d["id"]] = d
    rkp = os.path.join(course, "ranking.json")
    ranking = jl(rkp) if os.path.isfile(rkp) else []
    vp = os.path.join(course, "_verify", "results.json")
    checks = jl(vp)["checks"] if os.path.isfile(vp) else []
    btp = os.path.join(course, "_audit", "backtest.json")
    bt = jl(btp) if os.path.isfile(btp) else {"calibrated": False}
    code, name = cfg.get("course_code", ""), cfg.get("course_name", "")
    out = os.path.join(course, "build")
    img = os.path.join(out, "img")
    os.makedirs(img, exist_ok=True)
    roots = [cfg.get("root"), course]
    cache, errors = {}, []
    lint_terms(course, ledger, ev, errors)

    def quote_row(i):
        v = ev[i]
        ar = v.get("claim", "") if lang == "en" else (v.get("claim_ar") or v.get("claim", ""))
        return ('<div class="q"><b>%s</b> %s %s <span class="t">%s @%s</span><br>%s<br><span class="ltr">"%s"</span></div>' % (
            e(SPK_AR.get(v.get("speaker"), "")), e(TYPE_AR.get(v.get("type"), "")), e(i), e(os.path.basename(v.get("media", ""))[:34]),
            mmss(v.get("t_start")), e(ar), e(v.get("quote", ""))))

    def images_for(item_id, src, spec, item=None):
        path = bc.find_source(src, roots, cache)
        if not path:
            errors.append("%s: source file %s not found under root" % (item_id, src))
            return ""
        if not path.lower().endswith(".pdf"):
            dst = "%s_src%s" % (item_id, os.path.splitext(path)[1])
            shutil.copyfile(path, os.path.join(img, dst))
            return '<img src="img/%s">' % e(dst)
        h = ""
        for pg in bc.pages_of(spec):
            fn = "%s_p%d.png" % (item_id, pg)
            crop = (item.get("crop_start"), item.get("crop_end")) if item and pg == bc.bc_first(spec) else None
            err = bc.render(path, pg, os.path.join(img, fn), dpi, crop)
            if err:
                errors.append("%s: %s (%s)" % (item_id, err, src))
                continue
            h += '<img src="img/%s"><div class="src">%s, page %d</div>' % (e(fn), e(src), pg)
        return h

    # ---------- cover
    body = '<div class="hdr"><small>جامعة حورس بمصر — كلية الهندسة</small><h1>الكبسولة الشاملة — %s (%s)</h1>' % (e(name), e(code))
    body += "<div>أستاذ المادة: %s — الامتحان: %s</div>" % (e(str(cfg.get("instructor", "-"))), e(str(cfg.get("exam", {}).get("date", "-"))))
    body += "<div>الملف مرتّب تنازليًا حسب الأولوية، وكل ادعاء بيرجع لتسجيل وتوقيت وجملة حرفية، وكل رقم اتحسب تاني بشكل مستقل.</div></div>"
    banner = cfg.get("banner") or ledger.get("evidence_note") or ""
    cal = ("معايرة على امتحانات قديمة: " + "؛ ".join("%s نسبة الإصابة %s" % (k, v["hit_rate_confirmed_likely"]) for k, v in bt.get("exams", {}).items())
           if bt.get("calibrated") else "الترتيب غير معاير (مفيش امتحانات قديمة). النسبة اللي جنب كل مسألة تقدير لقوة الأدلة (كلام الدكتور والمعيد وتكرار المسألة)، مش احتمال حقيقي ومش ضمان.")
    body += '<div class="box honest"><b>اقرأ الأول — حدود الملف:</b><br>%s<br>%s</div>' % (e(cal), '<span class="ltr">%s</span>' % e(banner) if banner else "")

    # ---------- section 1: what was said
    body += '<div class="sec">القسم الأول: اللي قاله الدكتور والمعيد (بالتسجيل والتوقيت)</div>'
    for typ in TYPE_ORDER:
        rows = [v for v in ev.values() if v.get("type") == typ]
        if not rows:
            continue
        rows.sort(key=lambda v: (0 if v.get("speaker") == "doctor" else 1, v.get("media", ""), v.get("t_start", 0)))
        body += '<div class="box %s"><b>%s</b>%s</div>' % ("honest" if typ == "exclusion" else "", e(TYPE_AR[typ]), "".join(quote_row(v["id"]) for v in rows))

    # ---------- section 2: problems ranked
    probs = {p["id"]: p for m in ledger["modules"] for p in m.get("problems", [])}
    rk = {x["id"]: x for x in ranking}
    order = [x["id"] for x in ranking if x["id"] in probs] + [i for i in probs if i not in rk]
    body += '<div class="sec pb">القسم الثاني: المسائل مرتبة بالأولوية (الحل + صورة الصفحة الأصلية)</div>'
    for n, pid in enumerate(order, 1):
        p = probs[pid]
        steps, expl = p.get("solution_steps") or [], p.get("explain_" + lang)
        if not steps:
            errors.append("%s: no solution_steps in ledger" % pid)
        if not expl:
            errors.append("%s: no explain_%s in ledger" % (pid, lang))
        ok = [c for c in checks if c["id"].split("/")[0] == pid]
        tier = rk.get(pid, {}).get("tier", "possible")
        badges = '<span class="b-%s">%s%s</span>' % (tier if tier in TIER_AR else "possible", TIER_AR.get(tier, tier),
                                                      " — ثقة تقديرية %d%%" % rk[pid].get("pct", 0) if pid in rk else "")
        spk = sorted({ev[i].get("speaker") for i in p.get("evidence_ids", []) if i in ev})
        for s_ in spk:
            badges += '<span class="b-info">%s</span>' % e(SPK_AR.get(s_, s_))
        if ok and all(c.get("ok") for c in ok):
            badges += '<span class="b-ok">اتحسب تاني ✔ (%d)</span>' % len(ok)
        badges += where_spans(p, lang, errors)
        left = images_for(pid, p["source_file"], p["page_or_slide"], p)
        right = '<div class="pre"><b>فهم المسألة قبل الحل (Understand first):</b><br>%s</div>' % e(expl or "")
        right += '<div class="q">المصدر: <span class="t">%s — page/slide %s</span></div>' % (e(p["source_file"]), e(str(p["page_or_slide"])))
        sol = solution_html(p, lang, True, errors)
        warn = "".join('<div class="warn">%s</div>' % e(s_) for s_ in steps if s_.startswith(("WARNING", "NOTE")))
        spoken = "".join(quote_row(i) for i in p.get("evidence_ids", []) if i in ev) or '<div class="q">مفيش تسجيل مرتبط بالمسألة دي.</div>'
        body += ('<div class="card"><div class="top">Problem %d — %s</div><div class="body"><div class="badges">%s</div>'
                 '<div class="grid"><div>%s</div><div>%s</div></div><div class="sol">%s</div>%s'
                 '<div><b>اللي اتقال عنها:</b>%s</div></div></div>') % (n, e(p.get("title", pid)), badges, left, right, sol, warn, spoken)

    # ---------- section 3: formulas
    body += '<div class="sec pb">القسم الثالث: القوانين</div>'
    for m in ledger["modules"]:
        if m.get("formulas"):
            body += "<h3>%s</h3>" % e(m.get("title", ""))
            for f_ in m["formulas"]:
                shown = '<div class="tex">%s</div>' % e(f_["tex"]) if f_.get("tex") else e(f_.get("title", f_["id"]))
                body += '<div class="formula">%s<small>%s %s</small></div>' % (shown, e(f_.get("title", "")) if f_.get("tex") else "", e(f_.get("source", "")))

    # ---------- section 4: theory + traps
    body += '<div class="sec">القسم الرابع: النظرية والفخاخ</div>'
    for m in ledger["modules"]:
        items = m.get("theory_items", []) + [{"title": "⚠️ " + t["text"], "source": "", "evidence_ids": t.get("evidence_ids", [])} for t in m.get("traps", [])]
        if items:
            body += "<h3>%s</h3><ul>" % e(m.get("title", ""))
            for t in items:
                body += "<li>%s <small class='ltr'>%s</small></li>" % (e(t.get("title", t.get("id", ""))), e(t.get("source", "")))
            body += "</ul>"

    # ---------- section 5: practice paper
    pick = [i for i in order if rk.get(i, {}).get("tier") != "excluded"][:nexam]
    body += '<div class="sec">القسم الخامس: ورقة تدريب (الأسئلة بس — الحلول في القسم الثاني)</div><ol>'
    for pid in pick:
        body += "<li class='ltr'>%s</li>" % e(probs[pid].get("title", pid))
    body += "</ol>"

    if errors:
        print("BUILD FAILED (nothing written):")
        for x in errors:
            print("  - " + x)
        return 1
    kdst = os.path.join(out, "katex")
    if os.path.isdir(kdst):
        shutil.rmtree(kdst)
    shutil.copytree(os.path.join(HERE, "..", "assets", "katex"), kdst)
    mname = st_fname(cfg, "master", lang)
    hp = os.path.join(out, mname + ".html")
    doc_html = "<!doctype html><html lang=ar dir=rtl><meta charset=utf-8><title>%s Master</title>%s%s<body>%s</body></html>" % (e(code), KATEX, CSS, body)
    with open(hp, "w", encoding="utf-8") as f:
        f.write(to_en(doc_html) if lang == "en" else doc_html)
    mine = ("build/" + mname + ".html", "build/" + mname + ".pdf")
    delivs = [d for d in cfg.get("deliverables", []) if d not in mine] + [mine[0]]
    br = bc.find_browser()
    pdf = os.path.abspath(hp[:-5] + ".pdf")
    if not br:
        print("NOTE: no Edge/Chrome found, PDF skipped; HTML is complete")
    else:
        if os.path.isfile(pdf):
            os.remove(pdf)
        prof = tempfile.mkdtemp(prefix="hc_edge_")
        subprocess.run([br, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--user-data-dir=" + prof, "--virtual-time-budget=8000", "--print-to-pdf=" + pdf,
                        "file:///" + os.path.abspath(hp).replace(os.sep, "/")], capture_output=True, timeout=180)
        for _ in range(80):
            if os.path.isfile(pdf) and os.path.getsize(pdf) > 0:
                break
            time.sleep(0.5)
        shutil.rmtree(prof, ignore_errors=True)
        if os.path.isfile(pdf):
            import fitz
            doc = fitz.open(pdf)
            n = doc.page_count
            for i, pg in enumerate(doc):
                w, h = pg.rect.width, pg.rect.height
                pg.insert_text((w / 2 - 25, h - 14), "%s  |  %d / %d" % (code, i + 1, n), fontsize=8, color=(0.4, 0.4, 0.4))
            tmp = pdf + ".tmp"
            doc.save(tmp)
            doc.close()
            os.replace(tmp, pdf)
            delivs.append(mine[1])
            print("master PDF: %s (%d pages)" % (pdf, n))
        else:
            print("NOTE: PDF failed; HTML is complete")
    cfg["deliverables"] = delivs
    with open(os.path.join(course, "course.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("now run: validate.py %s --post-build" % course)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
