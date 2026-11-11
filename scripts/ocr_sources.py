"""OCR for scanned PDFs (pages with no text layer). Local only: Windows built-in OCR, nothing is uploaded.

Usage: python ocr_sources.py <course_dir> [--lang en-US] [--dpi 150] [--file NAME.pdf]

Scans every PDF under course.json `root` (or only --file). For each page without a text layer it renders a
PNG with PyMuPDF and runs scripts/ocr_win.ps1. Writes `_audit/ocr/<pdf name>.txt` with `=== page N ===`
sections (text-layer pages are copied as-is) so slides can feed the glossary and evidence quotes.
Output is OCR: it can contain mistakes, label it "OCR" wherever it is quoted.
Exit 0 ok, 1 on failure (with a one-line fix), 2 usage.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PS1 = os.path.join(HERE, "ocr_win.ps1")


def ocr_png(png, lang):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS1, png, lang],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    return r.returncode, r.stdout, r.stderr


def main(argv):
    if not argv or argv[0].startswith("-"):
        print("usage: ocr_sources.py <course_dir> [--lang en-US] [--dpi N] [--file NAME.pdf]")
        return 2
    course = argv[0]
    lang = argv[argv.index("--lang") + 1] if "--lang" in argv else "en-US"
    dpi = int(argv[argv.index("--dpi") + 1]) if "--dpi" in argv else 150
    only = argv[argv.index("--file") + 1] if "--file" in argv else None
    try:
        import fitz
    except ImportError:
        print("FAIL: PyMuPDF missing. Fix: pip install pymupdf")
        return 1
    if os.name != "nt":
        print("FAIL: ocr_sources.py uses the Windows built-in OCR. Fix: run it on Windows or supply text by hand")
        return 1
    with open(os.path.join(course, "course.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    root = cfg.get("root")
    if not root or not os.path.isdir(root):
        print("FAIL: course.json has no valid root. Fix: python scripts/preflight.py <course_dir>")
        return 1
    outdir = os.path.join(course, "_audit", "ocr")
    os.makedirs(outdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="hc_ocr_")
    done = scanned = 0
    for dp, _, files in os.walk(root):
        for fn in sorted(files):
            if not fn.lower().endswith(".pdf") or (only and fn != only):
                continue
            src = os.path.join(dp, fn)
            dst = os.path.join(outdir, fn + ".txt")
            if os.path.isfile(dst) and os.path.getmtime(dst) > os.path.getmtime(src):
                continue  # up to date
            doc = fitz.open(src)
            parts, n_ocr = [], 0
            for i in range(doc.page_count):
                txt = doc[i].get_text().strip()
                if len(txt) < 20:
                    png = os.path.join(tmp, "p%d.png" % i)
                    doc[i].get_pixmap(dpi=dpi).save(png)
                    code, out, err = ocr_png(png, lang)
                    if code == 3:
                        print("FAIL: Windows OCR language %s is not installed. Fix: Settings > Time & language > Language > add it (OCR)" % lang)
                        return 1
                    if code != 0:
                        print("FAIL: OCR error on %s p.%d: %s" % (fn, i + 1, err.strip()[:200]))
                        return 1
                    txt, n_ocr = out.strip(), n_ocr + 1
                    os.remove(png)
                parts.append("=== page %d%s ===\n%s" % (i + 1, " (OCR)" if len(doc[i].get_text().strip()) < 20 else "", txt))
            doc.close()
            with open(dst, "w", encoding="utf-8") as f:
                f.write("\n\n".join(parts) + "\n")
            done += 1
            scanned += n_ocr
            print("%s: %d pages, %d OCR" % (fn, len(parts), n_ocr))
    print("ocr_sources: %d PDF(s) written to %s (%d pages OCRed)" % (done, outdir, scanned))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
