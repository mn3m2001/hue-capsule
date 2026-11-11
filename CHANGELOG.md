# hue-capsule changelog

## v4 (2026-11-11), improvements made while testing on ECE321, ECE471 (Thermal)
Gatekeeper and tests
- `scripts/validate.py` + `gates.py`: hard gates (preflight, hydrate, transcripts, quality, evidence, ledger, verify, freshness); `tests/run_tests.py` self-test (good fixture + 12 broken fixtures + tool tests) must print SELF-TEST PASSED.
- `preflight.py` asks only what is missing; per-recording slide glossary; ASR hallucination, English-only-passage and foreign-script checks.
Evidence and review
- `draft_evidence.py` lists candidate moments (writes no evidence); `review_links.py` flags weak problem-to-evidence links (needs `link_basis`); `repair_transcripts.py`, `clean_transcripts.py`, `cross_check.py` (`--engine gemini|groq-turbo`).
- `ocr_sources.py` + `ocr_win.ps1`: local OCR with the Windows engine for scanned PDFs (handwriting is not recognised).
Scoring
- `score_topics.py`: per-course `scoring_overrides`, flat in-question-bank bonus skipped, `pct` = estimated confidence 0-100 from evidence strength (not a calibrated probability).
- `backtest.py`: runs automatically when past exams exist (`appeared_in` on ledger problems); skips with "not calibrated" otherwise; wired into `run_all.py`.
Build
- `build_capsule.py`: gated build of the 4 core files (+ `--exam N` predicted exam with model answer); source page image cropped to the problem (`crop_start` / `crop_end`); strict about missing solution steps or pages.
- `build_master.py`: ONE combined Arabic RTL master PDF (what the doctor/TA said with recording + time, problems ranked with source image, "understand before solving" box, steps, formulas, theory, practice paper), page numbers, offline math with bundled KaTeX (`assets/katex`).
- Shared style in `scripts/style.py` so every deliverable looks like the master.
Packaging
- `requirements.txt` and `scripts/setup.py` (checks everything, `--install` for Python packages); math library bundled, no CDN.
Packaging (cont.)
Deliverables (2026-11-11, user decision)
- Exactly four files: `1_Master`, `2_Formulas`, `3_Theory`, `4_Questions`. Formulas carry symbols/units and when-it-applies; theory items are explained and may have comparison tables; questions show every solution line with its explanation and common mistakes, then a practice paper with model answer.
- Master and Questions are built in Arabic and English (`--lang both`, `_EN` files); UI phrases are swapped by `style.to_en`, content comes from `*_en` ledger fields.
- Every problem shows where it is: `source_ref` (e.g. "Sheet 3 · Q3") + page, and `lecture_refs` (lecture slides where it is solved) as badges; the Master now also explains every solution step (same layout as the questions file): Givens, then each requirement with its steps and answer.
Output folder
- `scripts/package_output.py`: final folder named after the course with `PDF/` (the four PDFs + EN versions), `HTML/` (pages + img + katex) and `_evidence/`; refuses without a passing post-build validation or inside the Teams sync folder; a locked (open) PDF is saved as `_v2`.
Language rule
- In the Arabic files every course term, law, symbol and object name stays in English; Arabic is only the explanation. `term_map.json` (Arabic word -> English term) per course; `style.lint_terms` makes the builders fail when an Arabic explanation field still contains one. Structure labels are bilingual (e.g. المعطيات (Given)).
Less manual work
- `scripts/verify_kit.py`: SymPy kit; each `calc` is verified AND becomes a LaTeX line (symbolic formula, numbers, value), so the check and the printed equation come from one source; `--merge` fills `solution_tex` in the ledger.
- `scripts/draft_ledger.py`: drafts ledger problems from a text PDF (split by Q number, source_ref, crop_start/crop_end, givens_tex, asks); Arabic/English explanations, steps and answers stay yours.
Mixed Arabic/English layout
- `style.bidi_fix` isolates every English run inside Arabic text as a chip; the capsule explanation box now sits directly under the Given.

Explanation boxes
- Every solved problem gets a "Capsule explanation" box (own explanation + laws used) and every requirement a "How to solve it" line; both languages; enforced by the build and by tests. The language-rule lint now matches whole Arabic words.

File names and repo
- Files are named `<CODE>_<Short>_<Job>[_AR|_EN]` (course + function). `run_all.py` drafts ledger problems from `problem_sheets` in `course.json`; `verify_kit.save` never overwrites another verifier's `results.json` (writes `sympy_results.json`).
- Repo cleaned for sharing: personal skills, handoff notes and private paths removed; README, LICENSE, .gitignore added.

Applied on Thermal
- `verify_kit.calc` accepts plain numbers; `package_output` also copies the verification results and `term_map.json` into `_evidence/`. Thermal: 9 SymPy cross-checks (S1-03, S1-13, S2-03, S2-05, S2-19, S3-02, S3-04) agree with the scipy checks; run the kit in its own dir so it never overwrites `_verify/results.json`.
Known limits
- Evidence from a TA is weighted lower; no calibration without past exams; OCR does not read handwriting; the Gemini free quota can run out (429).
