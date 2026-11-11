# hue-capsule — exam "Capsule" builder (Claude skill)

Turns one university course (lecture recordings, slides, problem sheets, past exams) into a small set of exam-revision files
where **every claim is traceable**: each thing the doctor or TA said is tied to a recording, a timestamp and a verbatim quote,
and every number in a solved problem is re-computed with SymPy. A read-only gatekeeper refuses to build or say "done" until
all checks pass. Built for Horus University in Egypt (HUE) but nothing in it is specific to one course.

Arabic manual: [README_AR.md](README_AR.md) · Full rules the AI follows: [SKILL.md](SKILL.md) · History: [CHANGELOG.md](CHANGELOG.md)

---

## 1. What you get (per course)

Folder `<CODE>_<Course_Name>/`:

| File (example: ECE471 / Thermal) | What it is |
|---|---|
| `ECE471_Thermal_Master_Capsule_AR.pdf` / `_EN.pdf` | The main file: honesty box, what the doctor/TA said (recording + minute + quote), problems ranked by likelihood with an estimated confidence %, cropped source image, full solution, formulas, theory/traps, practice paper with model answer |
| `ECE471_Thermal_Formulas.pdf` | Every law typeset: symbols, units, when it applies and when not, source |
| `ECE471_Thermal_Theory.pdf` | Every concept explained, comparison tables, traps |
| `ECE471_Thermal_Solved_Questions_AR.pdf` / `_EN.pdf` | The most important questions in detail: Given → each requirement with its steps and answer, problem number, source page and lecture slide |
| `HTML/` | The same pages as HTML (open by double click, works offline) |
| `_evidence/` | Evidence list, ledger, ranking, verification results, self-review (for audit) |

Under every problem the Master and the Solved Questions files carry the doctor-based "Understand first" box, then a separate "Capsule explanation" box (the skill's own understanding of the subject, with the laws used) and a "How to solve it" line under each requirement.

Arabic files keep every course term, law and symbol **in English**; Arabic is only the explanation around them.

## 2. Honest limits (read this)

* The percentage on a problem is an **estimated confidence, not a probability**. With past exams the skill back-tests itself and
  reports a hit rate; without them every file says "not calibrated".
* Handwriting is not recognised by OCR; the page image stays the source of truth.
* Transcription of Arabic-English lectures is imperfect; the gate rejects bad transcripts and a model-chosen spot check is
  labelled "not human-heard" unless you listened.
* The AI writes the Arabic/English explanations; the scripts verify numbers, quotes, structure and the language rule, not the teaching quality.
  Skim the files before you rely on them.

## 3. Requirements

* Python 3.10+ and the packages in `requirements.txt` (`pymupdf`, `scipy`, `sympy`, `numpy`)
* `ffmpeg` (audio extraction), Microsoft Edge or Chrome (HTML → PDF)
* For transcription: environment variable `GROQ_API_KEY` (name checked only; never paste a key in chat). `openai` package for the Groq client.
  Optional second engine for the spot check: `GEMINI_API_KEY`.
* OCR of scanned slides uses the built-in Windows OCR (`scripts/ocr_win.ps1`); on other systems supply slide text another way.
* Math is typeset offline with the bundled KaTeX (`assets/katex`, MIT license).

Check everything: `python scripts/setup.py` (add `--install` to pip-install missing packages).

## 4. Install

1. Download or clone this repository.
2. Copy the folder to your Claude skills folder under the name `hue-capsule` (for Claude Code: `~/.claude/skills/hue-capsule`).
3. `pip install -r requirements.txt`, then `python scripts/setup.py`.
4. Run the self-test: `python tests/run_tests.py`. It must end with `SELF-TEST PASSED`. If it does not, stop: the gatekeeper is broken.

## 5. Use it (the short way)

Open Claude in a working folder and say, for example: *"Build the midterm capsule for ECE471."* The skill:

1. runs `preflight.py` (finds videos, slides, sheets; asks at most 3 questions, only about what it cannot find),
2. transcribes, checks transcript quality, builds the evidence list and the curriculum ledger,
3. verifies every number with SymPy, scores and ranks the problems, back-tests if past exams exist,
4. builds the PDFs/HTML, validates them, and packages the final folder.

You give it past exams or the doctor's quizzes when you have them: they are the single biggest accuracy gain.

## 6. The pipeline and its gates

`validate.py` runs the gates in order and stores the state in `capsule_state.json`; a stage cannot start before the previous gate passed.

| Gate | Passes when |
|---|---|
| `preflight` | sources found, tools present, secrets exist as env variables |
| `hydrate` | cloud-only (OneDrive placeholder) files are really on disk |
| `transcripts_exist` | every recording has a transcript with timestamps |
| `transcript_quality` | words/minute, glossary recall, language mix, no loops, spot check agrees |
| `evidence` | every evidence quote exists verbatim in the transcript window or PDF page |
| `ledger` | problems/formulas/theory carry the required fields and linked evidence |
| `verify` | every problem has a passing recomputation |
| `freshness` | every deliverable is newer than its inputs |

Typical commands (all from the skill folder; `<course>` is the run folder):

```bash
python scripts/preflight.py <course>
python scripts/transcribe.py <course>
python scripts/draft_evidence.py <course>          # lists candidate moments; you write evidence.jsonl
python scripts/draft_ledger.py <course> "sheet.pdf" --label "Sheet 1"
python scripts/verify_kit.py <course> --merge      # solution lines from the SymPy kit into the ledger
python scripts/run_all.py <course>                 # self-test, preflight, validate, draft sheets, score, backtest, link review
python scripts/build_capsule.py <course> --pdf --lang both
python scripts/build_master.py <course> --lang both
python scripts/validate.py <course> --post-build
python scripts/package_output.py <course> --dest "<where the final folder goes>"
```

## 7. Files inside a course run

```
<course>/
  course.json                    identity, root folder, exam date, media list, thresholds, short_name, problem_sheets
  evidence.jsonl                 one JSON per oral/slide claim (schema: references/schema.md)
  course_curriculum_ledger.json  modules: theory, formulas, problems (with solution_tex, steps_ar/en, parts, givens_tex)
  term_map.json                  Arabic word -> English term that must NOT appear in Arabic explanations
  ranking.json                   tier + estimated confidence per problem (from score_topics.py)
  _verify/                       results.json (+ sympy_results.json), the checks
  _audit/                        spot check, link review, self-review
  build/                         generated HTML/PDF (never edit by hand)
```

`templates/course.json` is a starting point. Useful fields: `short_name` (used in file names), `exam` (type/date/hall),
`thresholds` (e.g. `min_glossary_recall`, always disclosed in the files when relaxed), `problem_sheets`
(`[{"path": "...pdf", "label": "Sheet 1"}]`, drafted automatically by `run_all.py`), `scoring_overrides`.

## 8. How the ranking works

`references/scoring.json` holds the weights (the doctor said it will come, TA hints, repeated in past exams, in the question bank,
time spent in lectures, ...). `score_topics.py` turns the score into a tier (confirmed / likely / possible / excluded) and
`pct = 100 / (1 + exp(-(score - likely_threshold) / 2))`. `backtest.py` removes one past exam at a time and measures how many of its
problems the ranking would have caught.

## 9. Privacy

* Audio is sent to the transcription provider you approve (Groq by default); the optional spot check sends short windows to Google.
  The skill asks before using either.
* API keys are read from environment variables only and are never printed or stored.
* The skill never writes into a cloud-synced class folder and never overwrites your older files (a locked PDF is saved as `_v2`).

## 10. Contributing / tests

`python tests/run_tests.py` builds a small fixture course and 12 deliberately broken ones; the gatekeeper must accept the good one and reject
all broken ones. Add a test whenever you add a guardrail. Do not weaken a gate to make a course pass: fix the course.

License: MIT (see `LICENSE`). Bundled KaTeX 0.10.0 is MIT licensed.
