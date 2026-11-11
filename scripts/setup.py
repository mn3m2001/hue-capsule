"""Check (and optionally install) everything the skill needs. Usage:

    python scripts/setup.py            check only, prints one line per item, exit 0 when nothing required is missing
    python scripts/setup.py --install  also runs `pip install` for missing Python packages (downloads from PyPI)

Bundled inside the skill (nothing to install): assets/katex (math typesetting).
Needs the machine (cannot be bundled): Python 3.10+, ffmpeg, Edge or Chrome (HTML -> PDF), and for transcription
the environment variable GROQ_API_KEY (name only is checked; never paste a key in chat). GEMINI_API_KEY is optional
(second-engine spot check). On Windows the OCR engine is built in (OCR language en-US); other systems need to supply
slide text another way.
"""
import importlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKGS = [("fitz", "pymupdf"), ("scipy", "scipy"), ("sympy", "sympy"), ("numpy", "numpy")]


def have(mod):
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False


def main(argv):
    install = "--install" in argv
    rows, missing_required = [], []

    def add(name, ok, fix, required=True):
        rows.append((name, ok, fix, required))
        if required and not ok:
            missing_required.append(name)

    add("Python 3.10+", sys.version_info >= (3, 10), "install Python 3.10 or newer from python.org")
    todo = [pip for mod, pip in PKGS if not have(mod)]
    if todo and install:
        subprocess.run([sys.executable, "-m", "pip", "install", "--user"] + todo)
    for mod, pip in PKGS:
        add("python package %s" % pip, have(mod), "python scripts/setup.py --install  (or: pip install %s)" % pip)
    add("bundled KaTeX (assets/katex)", os.path.isfile(os.path.join(ROOT, "assets", "katex", "katex.min.js")),
        "the skill folder is incomplete: copy the assets folder back from the original skill")
    add("ffmpeg (audio extraction)", bool(shutil.which("ffmpeg")), "install ffmpeg and add it to PATH (winget install ffmpeg)")
    browser = any(shutil.which(n) for n in ("msedge", "chrome", "google-chrome", "chromium")) or any(
        os.path.isfile(p) for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                                    r"C:\Program Files\Google\Chrome\Application\chrome.exe"))
    add("Edge or Chrome (HTML -> PDF)", browser, "install Microsoft Edge or Google Chrome")
    add("env GROQ_API_KEY (transcription)", bool(os.environ.get("GROQ_API_KEY")),
        "set the environment variable GROQ_API_KEY (your own key; never type it in chat)")
    add("env GEMINI_API_KEY (optional spot check)", bool(os.environ.get("GEMINI_API_KEY")),
        "optional: set GEMINI_API_KEY, or use `cross_check.py --engine groq-turbo`", required=False)
    add("Windows OCR (scanned slides)", os.name == "nt", "optional: only available on Windows", required=False)
    for name, ok, fix, req in rows:
        print("[%s] %s%s" % ("ok" if ok else ("MISSING" if req else "optional"), name, "" if ok else "  -> " + fix))
    if missing_required:
        print("\nMISSING (required): " + "; ".join(missing_required))
        return 1
    print("\nALL REQUIRED ITEMS PRESENT")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
