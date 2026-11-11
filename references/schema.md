# evidence.jsonl (one JSON object per line)

```
{"id":"EV-01","claim":"short statement","type":"promise|exclusion|trap|emphasis|solved_in_class",
 "kind":"video","media":"<video path exactly as in course.json>","t_start":12.0,"t_end":18.0,
 "quote":"verbatim words from the transcript (3+ words)","speaker":"doctor|ta|slide","confidence":0.0-1.0}

{"id":"EV-02","claim":"...","type":"emphasis","kind":"pdf","file":"<path under course root>","page":4,
 "quote":"verbatim words from that page","speaker":"slide","confidence":0.9}
```
The gate rejects: missing fields, duplicate ids, t_end <= t_start, quote not present in the transcript within
+-5 s of the window (or on the PDF page), unknown media, unknown type or speaker.

# course_curriculum_ledger.json (fields the gates read)

- `modules[].theory_items[]`: `id`, `source`.
- `modules[].formulas[]`: `id`, `source` or `evidence_ids`.
- `modules[].problems[]`: `id`, `title`, `source_file`, `page_or_slide`, `evidence_ids[]` (required when
  `solved_by_instructor` or `instructor_context` is set), `sympy_verified` (needs a passing check with the same
  id in `_verify/results.json`), `recurrence_sources[]`, `in_question_bank`.
- Other fields (schematics, traps, lab safety, Arabic explanations) are free text in the ledger (see the README for the field list).

# spot_check.json
`{"entries":[{"media":"<video path>","t":123.0,"ok":true,"heard":"optional note"}]}` - at least 10, all ok.
Produced by a human listening to moments the agent lists (timestamp + transcript text).
