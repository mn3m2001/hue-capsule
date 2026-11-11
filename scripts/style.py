"""Shared look of every deliverable (Arabic RTL, KaTeX math offline, same cards and badges as the master PDF)."""
import html
import os
import re
import shutil

e = html.escape
HERE = os.path.dirname(os.path.abspath(__file__))
TYPE_AR = {"exclusion": "🛑 مش داخل في الامتحان", "promise": "🎯 وعد / شرط من الدكتور", "emphasis": "⚡ تشديد",
           "trap": "⚠️ فخ", "solved_in_class": "✅ اتحل في الشرح"}
TYPE_ORDER = ["exclusion", "promise", "emphasis", "trap", "solved_in_class"]
SPK_AR = {"doctor": "الدكتور", "ta": "المعيد", "slide": "السلايد"}
TIER_AR = {"confirmed": "مؤكد", "likely": "مرجّح", "possible": "محتمل", "excluded": "مستبعد"}
CSS = """<style>
@page{size:A4;margin:12mm 12mm 16mm 12mm}
body{font-family:'Segoe UI','Cairo',Tahoma,Arial,sans-serif;direction:rtl;line-height:1.7;color:#1d2a2e;font-size:13px;margin:0}
.hdr{border:2px solid #0b6e72;border-radius:8px;padding:10px 14px;margin-bottom:10px;background:#f4fbfb}
.hdr small{color:#0b6e72}.hdr h1{margin:6px 0;color:#0b4f52;font-size:22px}
.sec{background:#0b4f52;color:#fff;padding:7px 12px;border-radius:6px;margin:16px 0 8px;font-size:17px;break-after:avoid}
.box{border:1px solid #cfd8dc;border-radius:6px;padding:8px 12px;margin:8px 0}
.honest{border:2px solid #c0392b;background:#fff4f2}.green{border:2px solid #2e8b57;background:#f2fbf5}
.card{border:1px solid #b9c7cb;border-radius:8px;margin:12px 0;overflow:hidden}
.card .top{background:#0b6e72;color:#fff;padding:6px 12px;font-weight:bold;direction:ltr;text-align:left;font-size:14px}
.card .body{padding:8px 12px}
.badges span{display:inline-block;border-radius:10px;padding:1px 9px;margin:2px 3px;font-size:11px;font-weight:bold;color:#fff}
.b-confirmed{background:#c0392b}.b-likely{background:#e67e22}.b-possible{background:#7f8c8d}.b-info{background:#2c7a9b}.b-ok{background:#2e8b57}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px}
.grid img{width:100%;border:1px solid #999;break-inside:avoid}.src{font-size:11px;color:#666;direction:ltr;text-align:left}
.pre{background:#fff8e6;border:1px solid #f0c36d;border-radius:6px;padding:6px 10px;margin:6px 0}
.sol{direction:ltr;text-align:left;background:#f4f7fb;border-left:4px solid #0b6e72;border-radius:4px;padding:6px 12px;margin:6px 0;font-family:Cambria,'Times New Roman',serif;font-size:13.5px}
.sol ol{margin:4px 0;padding-left:20px}.sol li{margin:3px 0}
.warn{background:#fff0ee;border:1px solid #e3a69d;border-radius:4px;padding:4px 10px;margin:5px 0;direction:ltr;text-align:left;font-size:12px}
.q{font-size:12px;color:#33454a;margin:3px 0}.q .t{direction:ltr;unicode-bidi:isolate;font-family:Consolas,monospace;font-size:11px;color:#0b4f52}
.formula{direction:ltr;text-align:left;font-family:Cambria,'Times New Roman',serif;background:#f4f7fb;border:1px solid #d5dde2;border-radius:4px;padding:4px 10px;margin:4px 0}
.how{background:#eef3fb;border-right:3px solid #7a96c9;border-radius:4px;padding:3px 8px;margin:3px 0 5px;font-size:12px}.insight{background:#f3effb;border:1px solid #b9a8e0;border-radius:6px;padding:6px 12px;margin:8px 0}.insight ul{margin:4px 0;padding-right:18px}.law{border-top:1px dashed #cdbfe9;padding:3px 0}.law .ar{direction:rtl;text-align:right;font-size:12px;color:#33454a}.ltr{direction:ltr;unicode-bidi:isolate;display:inline-block;background:#eef1f4;border-radius:4px;padding:0 4px;margin:0 2px;font-size:.95em}.tex .ltr,.ask .ltr,.hdr .ltr{background:none;padding:0}.given{background:#eef6ee;border:1px solid #b7d7b7;border-radius:6px;padding:4px 10px;margin:6px 0}.part{border:1px solid #cfd8dc;border-radius:6px;margin:8px 0;padding:4px 10px;background:#fff}.ask{background:#e6f1f2;border-radius:4px;padding:3px 8px;margin:2px 0 4px;font-weight:bold}.ans{background:#fff4d6;border:1px solid #f0c36d;border-radius:4px;padding:3px 10px;margin:4px 0;font-weight:bold}.ans .tex{display:inline-block;margin:0 8px}.step{border-bottom:1px dashed #cfd8dc;padding:3px 0}.step .ar{direction:rtl;text-align:right;font-family:"Segoe UI",Tahoma,sans-serif;font-size:12px;color:#33454a;margin:0 0 4px}.tex{direction:ltr;text-align:left;margin:2px 0;font-size:.86em}.tex .katex-display{margin:3px 0;text-align:left}.tex .katex-display>.katex{text-align:left}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #cfd8dc;padding:4px 7px;vertical-align:top;font-size:12px}th{background:#e6f1f2}
.pb{break-before:page}
</style>"""


KATEX = ('<link rel="stylesheet" href="katex/katex.min.css"><script src="katex/katex.min.js"></script>'
         '<script>document.addEventListener("DOMContentLoaded",function(){var k=window.katex;if(!k){return;}'
         'document.querySelectorAll(".tex").forEach(function(el){try{k.render(el.textContent.trim(),el,{displayMode:true,throwOnError:false});}catch(x){}});});</script>')




def mmss(t):
    return "%d:%02d" % (int(t // 60), int(t % 60)) if isinstance(t, (int, float)) else ""


def quote_row(v, vid=None, lang="ar"):
    """One spoken-evidence row: speaker, type, id, recording @time, Arabic claim, verbatim quote."""
    ar = v.get("claim", "") if lang == "en" else (v.get("claim_ar") or v.get("claim", ""))
    return ('<div class="q"><b>%s</b> %s %s <span class="t">%s @%s</span><br>%s<br><span class="ltr">"%s"</span></div>' % (
        e(SPK_AR.get(v.get("speaker"), "")), e(TYPE_AR.get(v.get("type"), "")), e(vid or v.get("id", "")),
        e(os.path.basename(v.get("media", ""))[:34]), mmss(v.get("t_start")), e(ar), e(v.get("quote", ""))))


def tex_or_text(tex, text):
    return '<div class="tex">%s</div>' % e(tex) if tex else e(text)


def copy_katex(out_dir):
    dst = os.path.join(out_dir, "katex")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(HERE, "..", "assets", "katex"), dst)


_LAT = re.compile(r"\([^()؀-ۿ]*[A-Za-z0-9][^()؀-ۿ]*\)|\[[^\[\]؀-ۿ]*[A-Za-z0-9][^\[\]؀-ۿ]*\]|[A-Za-z0-9](?:[A-Za-z0-9_\-+*/=<>^.,:;%°'’×· ]*[A-Za-z0-9%°])?")


def bidi_fix(html_text):
    """Mixed Arabic/English: wrap every run of Latin text/numbers inside the Arabic text in <span class=ltr> (direction:ltr; unicode-bidi:isolate),
    so the browser lays out each English term as one left-to-right block inside the right-to-left sentence instead of shuffling them.
    Math (.tex), <script>, <style>, <title> and tag attributes are not touched. Chromium already implements the Unicode bidi algorithm,
    so no extra bidi library is needed (python-bidi/arabic-reshaper are for engines that do not, and would reorder twice here)."""
    out, skip_until = [], None
    for tok in re.split(r"(<[^>]+>)", html_text):
        if tok.startswith("<"):
            out.append(tok)
            m = re.match(r"<\s*(/?)([a-zA-Z0-9]+)([^>]*)>", tok)
            if m and not m.group(1) and skip_until is None:
                if m.group(2).lower() in ("script", "style", "title") or re.search(r'class="(?:[^"]* )?tex(?: [^"]*)?"', m.group(3)):
                    skip_until = m.group(2).lower()
            elif m and m.group(1) and skip_until == m.group(2).lower():
                skip_until = None
            continue
        if skip_until or not re.search(r"[؀-ۿ]", tok):
            out.append(tok)  # no Arabic in this text node: nothing to isolate
        else:
            out.append(_LAT.sub(lambda mm: '<span class="ltr">%s</span>' % mm.group(0), tok))
    return "".join(out)


def document(title, body):
    return ("<!doctype html><html lang=ar dir=rtl><meta charset=utf-8><title>%s</title>%s%s<body>%s</body></html>"
            % (e(title), KATEX, CSS, body))


def header(code, name, instructor, exam, subtitle):
    return ('<div class="hdr"><small>جامعة حورس بمصر — كلية الهندسة</small><h1>%s — %s (%s)</h1>'
            '<div>أستاذ المادة: %s — الامتحان: %s</div></div>' % (e(subtitle), e(name), e(code), e(str(instructor or "-")), e(str(exam or "-"))))


# ---------- English version: content fields come from *_en; fixed UI phrases are swapped here
EN = {
 "جامعة حورس بمصر — كلية الهندسة": "Horus University in Egypt — Faculty of Engineering",
 "الكبسولة الشاملة": "Complete Capsule", "المعطيات (Given):": "Given:", "المطلوب (Required)": "Required", "الإجابة (Answer):": "Answer:", "أستاذ المادة:": "Instructor:", "الامتحان:": "Exam:",
 "الملف مرتّب تنازليًا حسب الأولوية، وكل ادعاء بيرجع لتسجيل وتوقيت وجملة حرفية، وكل رقم اتحسب تاني بشكل مستقل.":
     "Ordered by priority. Every claim points to a recording, a time and a verbatim quote; every number was recomputed independently.",
 "معايرة على امتحانات قديمة: ": "Calibrated on past exams: ", "نسبة الإصابة": "hit rate",
 "الترتيب غير معاير (مفيش امتحانات قديمة). النسبة اللي جنب كل مسألة تقدير لقوة الأدلة (كلام الدكتور والمعيد وتكرار المسألة)، مش احتمال حقيقي ومش ضمان.":
     "Ranking is NOT calibrated (no past exams). The percentage beside each problem estimates evidence strength (what the doctor and TA said, recurrence); it is not a real probability and not a guarantee.",
 "الترتيب غير معاير (مفيش امتحانات قديمة): ده ترتيب احتمالات مش ضمان.": "Ranking is NOT calibrated (no past exams): a ranked likelihood, not a guarantee.",
 "اقرأ الأول — حدود الملف:": "Read first — limits of this file:",
 "القسم الأول: اللي قاله الدكتور والمعيد (بالتسجيل والتوقيت)": "Part 1: What the doctor and the TA said (recording and time)",
 "القسم الثاني: المسائل مرتبة بالأولوية (الحل + صورة الصفحة الأصلية)": "Part 2: Problems ranked by priority (solution + original page image)",
 "القسم الثالث: القوانين": "Part 3: Formulas", "القسم الرابع: النظرية والفخاخ": "Part 4: Theory and traps",
 "القسم الخامس: ورقة تدريب (الأسئلة بس — الحلول في القسم الثاني)": "Part 5: Practice paper (questions only — solutions are in Part 2)",
 "فهم المسألة قبل الحل (Understand first):": "Understand the problem first:", "شرح الكبسولة للمسألة (Capsule explanation):": "Capsule explanation of the problem:", "من فهمنا للمادة وليس من كلام الدكتور": "from our understanding of the subject, not from what the doctor said", "القوانين المستخدمة (Laws used):": "Laws used:", "طريقة حل المطلوب (How to solve it):": "How to solve it:", "المصدر:": "Source:", "اللي اتقال عنها:": "What was said about it:",
 "مفيش تسجيل مرتبط بالمسألة دي.": "No recording is linked to this problem.",
 "ثقة تقديرية": "est. confidence", "اتحسب تاني ✔": "recomputed ✔",
 "🛑 مش داخل في الامتحان": "🛑 Not in the exam", "🎯 وعد / شرط من الدكتور": "🎯 Promise / condition", "⚡ تشديد": "⚡ Emphasis",
 "⚠️ فخ": "⚠️ Trap", "✅ اتحل في الشرح": "✅ Solved in class",
 "الدكتور": "Doctor", "المعيد": "TA", "السلايد": "Slide", "مؤكد": "Confirmed", "مرجّح": "Likely", "محتمل": "Possible", "مستبعد": "Excluded",
 "أهم الأسئلة مشروحة بالتفصيل": "Key questions explained in detail",
 "مرتبة بقوة الأدلة. النسبة تقدير مش احتمال حقيقي. كل خطوة جنبها شرحها بالعربي.": "Ranked by evidence strength. The percentage is an estimate, not a real probability. Every step has its explanation.",
 "أخطاء شائعة (Common mistakes):": "Common mistakes:", "ورقة تدريب (الامتحان المتوقع)": "Practice paper (predicted exam)",
 "ملحوظة: صورة المصدر ممكن تكون فيها خطوات الحل أصلاً.": "Note: a source image may already show the worked solution.",
 "الإجابة النموذجية": "Model answer",
}


def to_en(html_text):
    for k in sorted(EN, key=len, reverse=True):
        html_text = html_text.replace(e(k), EN[k]).replace(k, EN[k])
    return html_text.replace("<html lang=ar dir=rtl>", "<html lang=en dir=ltr>").replace(
        "</style>", "body{direction:ltr}.step .ar{direction:ltr;text-align:left}</style>", 1)


KIND_NAME = {"master": "Master_Capsule", "formulas": "Formulas", "theory": "Theory", "questions": "Solved_Questions"}


def fname(cfg, kind, lang=None):
    """File name that says the course and the job: <CODE>_<Short>_<Job>[_AR|_EN] (no extension).
    `short_name` in course.json is used when present, else the first three words of course_name."""
    short = cfg.get("short_name") or "_".join(str(cfg.get("course_name", "")).split()[:3])
    short = re.sub(r"[^A-Za-z0-9]+", "_", short).strip("_")
    base = "_".join(x for x in (str(cfg.get("course_code", "COURSE")), short, KIND_NAME[kind]) if x)
    return base + ("_%s" % lang.upper() if lang and kind in ("master", "questions") else "")


def langs_of(argv):
    v = argv[argv.index("--lang") + 1] if "--lang" in argv else "ar"
    return ["ar", "en"] if v == "both" else [v]


def solution_html(p, lang, explain, errors):
    """Layout of one solved problem: Givens first, then every requirement with its steps and its answer underneath."""
    pid = p.get("id", "?")
    tex, giv, parts = p.get("solution_tex") or [], p.get("givens_tex") or [], p.get("parts") or []
    sar = p.get("steps_" + lang) or []
    if not giv:
        errors.append("%s: no givens_tex in the ledger (list of LaTeX lines)" % pid)
    if not parts:
        errors.append("%s: no parts in the ledger (each: ask_ar, ask_en, steps [first,last], answer_tex)" % pid)
    if not tex:
        errors.append("%s: no solution_tex in the ledger" % pid)
    covered = []
    h = '<div class="given"><b>المعطيات (Given):</b>%s</div>' % "".join('<div class="tex">%s</div>' % e(g) for g in giv)
    h += insight_html(p, lang, errors)  # the capsule's explanation sits right under the Given
    letters = len(parts) > 1
    for k, part in enumerate(parts):
        a, b = part["steps"]
        covered += list(range(a, b + 1))
        ask = part.get("ask_" + lang)
        if not ask:
            errors.append("%s: part %d has no ask_%s" % (pid, k + 1, lang))
        how = part.get("how_" + lang)
        if not how:
            errors.append("%s: part %d has no how_%s (one or two lines: how this requirement is solved)" % (pid, k + 1, lang))
        steps = '<div class="how"><b>طريقة حل المطلوب (How to solve it):</b> %s</div>' % e(how or "")
        for i in range(a, b + 1):
            if i >= len(tex):
                errors.append("%s: part %d step index %d is outside solution_tex" % (pid, k + 1, i))
                continue
            steps += '<div class="step"><div class="tex">%s</div>%s</div>' % (e(tex[i]), ('<div class="ar">%s</div>' % e(sar[i]) if explain and i < len(sar) else ""))
        h += ('<div class="part"><div class="ask"><b>المطلوب (Required)</b>%s: %s</div>%s<div class="ans"><span>الإجابة (Answer):</span><span class="tex">%s</span></div></div>'
              % ((" (%d)" % (k + 1)) if letters else "", e(ask or ""), steps, e(part.get("answer_tex", ""))))
    if tex and sorted(covered) != list(range(len(tex))):
        errors.append("%s: parts must cover every solution_tex line exactly once (covered %s of %d lines)" % (pid, sorted(covered), len(tex)))
    return h


def insight_html(p, lang, errors):
    """The capsule's own explanation box under a solved problem: idea, why this method, the laws used (with symbols and when they apply), the trap.
    Written from understanding of the subject, NOT from what the doctor said (so it is labelled as such). Ledger: `insight_<lang>` (>= 3 lines)
    and `insight_laws` = [{"tex", "note_ar", "note_en"}]."""
    pid = p.get("id", "?")
    lines = p.get("insight_" + lang) or []
    laws = p.get("insight_laws") or []
    if len(lines) < 3:
        errors.append("%s: insight_%s needs at least 3 lines (the capsule's own explanation of the problem)" % (pid, lang))
    if not laws:
        errors.append("%s: insight_laws is empty (list of {tex, note_ar, note_en}: the laws used in this problem)" % pid)
    h = '<div class="box insight"><b>شرح الكبسولة للمسألة (Capsule explanation):</b> <i>من فهمنا للمادة وليس من كلام الدكتور</i><ul>'
    h += "".join("<li>%s</li>" % e(x) for x in lines) + "</ul>"
    if laws:
        h += '<div class="laws"><b>القوانين المستخدمة (Laws used):</b>'
        for i, lw in enumerate(laws):
            note = lw.get("note_" + lang)
            if not lw.get("tex") or not note:
                errors.append("%s: insight_laws[%d] needs tex and note_%s" % (pid, i, lang))
            h += '<div class="law"><div class="tex">%s</div><div class="ar">%s</div></div>' % (e(lw.get("tex", "")), e(note or ""))
        h += "</div>"
    return h + "</div>"


def where_spans(p, lang, errors):
    """Badges: where the problem is (sheet/lecture number + page) and in which lecture slides it is solved."""
    ref = p.get("source_ref")
    if not ref:
        errors.append("%s: no source_ref in the ledger (e.g. 'Sheet 3 · Q3'; optional lecture_refs like 'Lec 5 · slide 23')" % p.get("id", "?"))
    word = "page" if lang == "en" else "صفحة"
    h = '<span class="b-info">📄 %s · %s %s</span>' % (e(ref or ""), word, e(str(p.get("page_or_slide", ""))))
    for r in p.get("lecture_refs", []):
        h += '<span class="b-ok">🎓 %s</span>' % e(r)
    return h


def _ar_strings(obj, path=""):
    """Yield (path, text) for every string stored under a key that ends with _ar."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.endswith("_ar") or k in ("ask_ar", "symbols_ar", "when_ar"):
                for t in _flat(v):
                    yield "%s.%s" % (path, k), t
            else:
                for r in _ar_strings(v, "%s.%s" % (path, k)):
                    yield r
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            for r in _ar_strings(v, "%s[%d]" % (path, i)):
                yield r


def _flat(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            for y in _flat(x):
                yield y


def lint_terms(course, ledger, evidence, errors):
    """Language rule: every course term (terms, laws, object names) stays in English; Arabic is only the explanation.
    `term_map.json` in the course folder lists Arabic words that must NOT appear, each with the English term to use."""
    import json
    mp = os.path.join(course, "term_map.json")
    if not os.path.isfile(mp):
        errors.append("term_map.json missing in the course folder ({\"arabic word\": \"english term\"}); it lists the Arabic words that must be written in English")
        return
    tmap = json.load(open(mp, encoding="utf-8"))
    pools = [("ledger", ledger)] + [("evidence " + i, v) for i, v in evidence.items()]
    for where, obj in pools:
        for path, text in _ar_strings(obj, where):
            for ar, en in tmap.items():
                if re.search(r"(?<![ء-ي])(?:لل|[بلوفك]?(?:ال)?)" + re.escape(ar) + r"(?![ء-ي])", text):  # whole word, so 'كرة' does not match 'فكرة'
                    errors.append("%s: Arabic term '%s' in the explanation: write '%s' in English instead" % (path, ar, en))
                    break
