---
name: hue-capsule
description: Build an evidence-backed exam mastery pack (الكبسولة / Capsule) for one university course (built for Horus University in Egypt, works for any course) from Teams materials and lecture/section recordings. Every oral claim is tied to a video file + timestamp + verbatim quote, every number is SymPy-verified, and a read-only gatekeeper blocks any build or "done" claim until all gates pass. Use for a capsule, midterm/final revision pack, or exam prediction for any HUE course.
---

# Hue | Capsule v4

Rules are enforced by scripts in `scripts/`, not by promises. Run them from the skill folder. NEVER edit,
copy-and-weaken, or bypass anything in `scripts/` or `tests/` during a course run. If a gate is wrong, stop
and tell the user; do not "fix" it to pass.

## 0. Before anything
1. `python tests/run_tests.py` must end with `SELF-TEST PASSED`. If not, stop: the gatekeeper is broken.
2. Preflight (stage 0). NEVER guess a path or assume a file is missing: run
   `python scripts/preflight.py <course_dir> [--speed]`. It auto-discovers the Teams root, videos, slides,
   question bank and environment (ffmpeg, PyMuPDF, transcription path, disk), and writes `course.json`.
   - exit 0: nothing missing, continue without asking anything.
   - exit 3: send the returned questions to the user in ONE message (max 3, numbered, default marked, answer
     by number). Save each answer with `python scripts/preflight.py <course_dir> --answer key=value`
     (e.g. `calibration=none`, `root=<path>`, `exam_date=2026-11-12`). Re-run until exit 0.
   - exit 1: an environment item cannot be fixed by an answer; show its one-line fix and stop.
   Secrets are checked by variable NAME only; never ask for a key in chat.
   `<course_dir>` = a working folder for the course run (any path you choose). Deletions go to the Recycle Bin only.
3. Tell the user how you understood the task and ask to proceed (big or irreversible steps only).
4. Student-facing style: plain Egyptian Arabic, English terms and paths in code blocks; progress as
   "step N of 12: ..." in simple words; every failure is one line plus the fix; the final report is max 5
   lines (what was built, which file to open first, what is uncertain, what is needed from the user).
   Technical details stay in files.

## 1. Pipeline (each stage needs the previous one; state lives in `capsule_state.json`)
| # | Stage | What to do | Gate |
|---|---|---|---|
| 0 | Preflight | `scripts/preflight.py` (see section 0): discover, ask only what is missing | `preflight` |
| 1 | Hydrate | list every video/audio/PDF; read 1 KB head/mid/tail | `hydrate`: any cloud placeholder = STOP, tell the user in the first line |
| 2 | Inventory | table of lectures, sheets, sections, question bank, labs; ask the user for missing calibration material (past exams, quizzes, section questions) | user confirms |
| 3 | Glossary | if a PDF has no text layer run `python scripts/ocr_sources.py <course_dir>` (local Windows OCR, writes `_audit/ocr/*.txt`; handwriting is NOT recognised, the page image is the source of truth); then build `glossary.txt` (30+ English technical terms) from slides/PDFs | `transcript_quality` needs it |
| 4 | Transcribe | `python scripts/transcribe.py <course_dir> [--provider groq]` (language auto, glossary as prompt, keys from env only) | `transcripts_exist` |
| 5 | Quality | gate checks words/min, glossary recall, English share, loops; `python scripts/cross_check.py <course_dir>` (12 windows re-transcribed by Gemini, key GEMINI_API_KEY, audio goes to Google: tell the user first) writes `_audit/spot_check.json`; any disagreement (`ok:false`) is listened to by the human, who sets `ok:true` + `heard` | `transcript_quality` |
| 5b | Repair | if the quality gate flags long English-only passages (ASR translated the speech) run `python scripts/repair_transcripts.py <course_dir>` (re-transcribes them with 2 other configs; unfixable ones go to `_audit/needs_human.json`) | `transcript_quality` |
| 6 | Evidence | `python scripts/draft_evidence.py <course_dir>` lists candidate moments (verbatim lines, suggested type; it writes no evidence); then write `evidence.jsonl` (schema: `references/schema.md`): claim + type + speaker + media + t_start/t_end + verbatim quote | `evidence`: quote must exist in the transcript window or PDF page |
| 7 | Ledger | `python scripts/draft_ledger.py <course_dir> "<sheet.pdf>" --label "Sheet 3"` drafts problems from a text PDF (ids, source_ref, crop text, givens, asks) into `_audit/ledger_draft.json`; you review and complete it. `course_curriculum_ledger.json`: theory, formulas, schematics, problems, traps, lab safety; link oral claims by `evidence_ids`; then `python scripts/review_links.py <course_dir>` (a link whose problem and claim share no keyword needs a written `link_basis`) | `ledger` |
| 8 | Verify | every number via SymPy with `scripts/verify_kit.py` (`Kit`, `problem().calc()`, `expect()`, `save()`): it writes `_verify/results.json` AND the typeset solution lines `_verify/steps.json`; `python scripts/verify_kit.py <course_dir> --merge` fills `solution_tex` in the ledger. Format of results: (`{"checks":[{"id":"PROB-01","ok":true}]}`) | `verify` |
| 9 | Predict | `python scripts/score_topics.py <course_dir>` -> `ranking.json` (confirmed / likely / possible / excluded, with reasons) | none; show the table to the user |
| 10 | Review | adversarial review (`the-fool`, or the running model reviewing itself if that skill is missing) of the predicted exam: list what could be wrong (weak evidence, TA-only sources, uncalibrated scoring). No council | findings fixed or listed |
| 10b | Humanize | run `humanizer` on explanatory prose only (intros, explanations, tips), in place on the drafts, before build. PROTECTED, never touched: evidence quotes, doctor/TA attributions with timestamps, formulas, numbers, units, circuit labels, code, file names. Afterwards re-run `validate.py`; any changed fact or quote = revert that paragraph | `validate.py` still exits 0 |
| 11 | Build | `python scripts/build_capsule.py <course_dir> --pdf --lang both` then `python scripts/build_master.py <course_dir> --lang both` (section 3) (`--exam N` adds the predicted exam paper + model answer from the top N ranked problems, labelled calibrated or not; runs `validate.py` first and refuses if it fails; needs `solution_steps` on every ledger problem; renders the source page PNG next to each problem; any missing step or page = exit 1) | deliverables |
| 12 | Audit | `python scripts/validate.py <course_dir> --post-build`; render page previews and look at them | `freshness` |

One command for the scripted stages (self-test, preflight, validate, score, link review; stops at the first failure with one fix line): `python scripts/run_all.py <course_dir>`. Per-course scoring weights: `scoring_overrides` in `course.json`; the `in_question_bank` bonus is skipped when every problem has it.

## 2. Hard rules
1. Never write "قال الدكتور" without an `evidence.jsonl` entry. Section recordings are usually the TA:
   set `speaker` honestly (`doctor`, `ta`, `slide`).
2. Never build PDFs before gates pass. A deliverable older than any transcript/evidence/ledger is stale.
3. The final acceptance report is the output of `validate.py`, printed verbatim. Do not write your own.
4. No warning-only passes. A missing audio file, transcript, quote or check is a failure.
5. Never claim database/real-run results from mocks; label anything simulated.
6. Calibration is automatic: `python scripts/backtest.py <course_dir>` (also run by `run_all.py`). Past exams found: mark `appeared_in` on the ledger problems each exam contained, and the script re-scores without that exam and prints the hit rate; report it. No past exams: it prints "not calibrated", the run continues normally with the available resources, and the capsule says "not calibrated".
   Exam prediction is a ranked likelihood, not a guarantee.
7. On any error or user correction: say it in the first line without defending, find the root cause (ask "why" up to five times), write one new guardrail, and add it to `tests/` when it can be tested. If you have an incident-learning skill installed, use it.
8. Secrets only from environment variables; never print or store them. Audio may be sent to the transcription
   provider the user approved (Groq); tell the user before using any other service.

## 2b. Final output location
When a course run passes all gates, package it: `python scripts/package_output.py <course_dir> --dest "<folder>"`
creates `<COURSE_CODE>_<Course_Name>/` with `PDF/` (the deliverables, Arabic and English), `HTML/` (the same pages with
`img/` and `katex/`, open by double click) and `_evidence/` (audit files, verification results, term map). `--dest` is
the student's course folder; never a cloud-synced class folder (the script refuses the Teams sync folder). Older files in the
destination are not touched; a PDF that is open in a viewer is saved as `name_v2.pdf` and reported.

## 3. Deliverables (exactly four kinds)
File names say the course and the job: `<CODE>_<Short>_<Job>[_AR|_EN]` (`short_name` in `course.json`, else the first
three words of the course name). Example for ECE471 / Thermal: `ECE471_Thermal_Master_Capsule_AR.pdf`.
1. `<CODE>_<Short>_Master_Capsule_AR / _EN` — the combined capsule: honesty box, what the doctor/TA said (recording + time + quote), problems ranked by
   priority with cropped source image, formulas, theory/traps, practice paper.
   RULE: under every problem the master shows the full explained solution: a "Understand first" box (Arabic/English), Givens, then each requirement with its steps, a one-line explanation under every step, and its answer (same layout as the Solved Questions file). The build fails if `explain_<lang>` or the steps are missing.
   RULE (capsule explanation): under every solved problem a separate purple box "Capsule explanation" holds the skill's OWN explanation, from understanding of the subject and not from the doctor (idea, why this method, trap), plus the laws used with symbols and when they apply. Ledger: `insight_ar` / `insight_en` (>= 3 lines each) and `insight_laws` = [{tex, note_ar, note_en}]. In the Master and Solved Questions files, Arabic and English versions.
   RULE (how to solve): under every "Required" a blue line "How to solve it" explains how that requirement is solved. Ledger: `how_ar` / `how_en` on every part. Missing any of these fails the build.
2. `<CODE>_<Short>_Formulas` — every law typeset, its symbols and units, when it applies and when not, source.
3. `<CODE>_<Short>_Theory` — every concept explained, comparison tables, traps.
4. `<CODE>_<Short>_Solved_Questions_AR / _EN` — the most important questions explained in detail: understand-first box, every solution line with
   its explanation, common mistakes, spoken evidence, then a practice paper with model answer.
Build: `python scripts/build_capsule.py <course_dir> --pdf --lang both` (formulas, theory, questions) then
`python scripts/build_master.py <course_dir> --lang both` (master), then `validate.py --post-build`, then
`python scripts/package_output.py <course_dir> --dest <folder>` (section 2b).
Language rule: in the Arabic files every course term, law, symbol, unit and object name (fin, window, pan, resistance, efficiency...) stays in ENGLISH exactly as in the slides; Arabic is only the explanation around them. Structure labels are bilingual (e.g. المعطيات (Given)). The course folder holds `term_map.json` ({arabic word: english term}); the builders fail when an Arabic explanation field still contains one of those words.
Ledger fields the builders require (a missing one is exit 1, never a silent gap): problems `solution_tex` (LaTeX lines),
`steps_ar` / `steps_en` (one explanation per line), `explain_ar` / `explain_en`, optional `mistakes_ar` / `mistakes_en`,
`crop_start` / `crop_end`; formulas `tex`, `symbols_ar`, `when_ar`; theory items `explain_ar`; modules may carry `tables`;
evidence `claim` (English) and `claim_ar`. Math is typeset offline with the bundled KaTeX (`assets/katex`).
Optional extras only if asked: one-page sheet, drill cards with video links `file:///...mp4#t=<sec>` (untested in the
user's browser), keyframes via `ffmpeg` at evidence timestamps.
Design rules for PDFs: `references/design_system.md`. Math: KaTeX via `latex-math-typesetting`.
Source figures: every problem shows the original source page as an image (slide, sheet or exam page, rendered with PyMuPDF) next to the question text and the solution steps, so figures, tables and handwritten parts are never lost. Works for any course.
Figures you must redraw (only when no source image exists, e.g. a schematic in an electronics course): draw from code (SVG/matplotlib/schemdraw), never AI-generated images for technical diagrams.

## 4. Linked skills
Optional, used only if installed: a domain skill for the course subject, `anti-hallucination`, `verification-before-completion`, `the-fool` (adversarial review; stage 10 falls back to a self-review), `humanizer` (stage 10b may be skipped), a stage-handoff skill (new chat per stage). None is required.

## 5. Speed mode
If the exam is under 48 hours away: finish in this order, validating each before the next: one-page sheet,
priority problem bank (top `confirmed`), formula compendium, theory guide, predicted exam.
