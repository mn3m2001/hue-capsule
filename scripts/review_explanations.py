"""Second-model review of the EXPLANATION text (not the numbers). Usage:

    python review_explanations.py <course_dir> [--engine groq|gemini] [--model NAME]

For every ledger problem it sends the English explanation (explain_en, steps_en, insight_en, how_en, law notes) together with the
givens, the solution lines and the answers to a different model family, and asks it to list technical errors, misleading statements,
claims the givens do not support, and contradictions with the answers. It does NOT rewrite anything.
Issues you judge wrong are recorded with the reason in `_audit/review_resolutions.json` ({problem id: why}); they show as "resolved".
Writes `_audit/explanation_review.json` ({model, problems: {id: {verdict: ok|issues, issues: [...]}}}); you read it, fix the ledger
text (or record why an issue is wrong), re-run until every verdict is ok, then mention the result in the final report.
Keys from the environment only (GROQ_API_KEY or GEMINI_API_KEY). The explanation text is sent to that provider: tell the user first.
"""
import json
import os
import sys
import time
import urllib.request

PROMPT = (
    "You are a strict reviewer of exam-preparation material for a university engineering course. You get ONE solved problem: "
    "the givens, the solution lines (LaTeX), the final answers, and the EXPLANATION text written for students. "
    "Check ONLY the explanation text against the solution: (1) technical errors, (2) misleading or oversimplified statements, "
    "(3) claims the givens do not support, (4) contradictions with the solution lines or answers, (5) wrong physical reasoning. "
    "Do not rewrite the text and do not comment on style. Reply with JSON only: "
    '{"verdict": "ok" | "issues", "issues": [{"where": "which sentence or field", "problem": "what is wrong", "suggestion": "how to fix"}]}. '
    "If everything is correct, verdict is ok and issues is an empty list."
)


def build_payload(p):
    """The text the reviewer sees for one problem (English fields only, so any model can judge it)."""
    parts = p.get("parts") or []
    return {
        "id": p.get("id"),
        "title": p.get("title"),
        "givens_tex": p.get("givens_tex"),
        "solution_tex": p.get("solution_tex"),
        "answers_tex": [x.get("answer_tex") for x in parts],
        "requirements": [x.get("ask_en") for x in parts],
        "explanation": {
            "understand_first": p.get("explain_en"),
            "steps": p.get("steps_en"),
            "capsule_explanation": p.get("insight_en"),
            "law_notes": [x.get("note_en") for x in p.get("insight_laws") or []],
            "how_to_solve_each_requirement": [x.get("how_en") for x in parts],
            "common_mistakes": p.get("mistakes_en"),
        },
    }


def parse_reply(text):
    """Accept a bare JSON reply or one wrapped in a code fence; anything else counts as a failed review."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):] if "{" in t else t
    try:
        d = json.loads(t[t.find("{"): t.rfind("}") + 1])
    except ValueError:
        return {"verdict": "error", "issues": [{"where": "reply", "problem": "reviewer reply was not JSON", "suggestion": text[:200]}]}
    issues = d.get("issues") or []
    verdict = "issues" if issues else ("ok" if d.get("verdict") == "ok" else "issues")
    return {"verdict": verdict, "issues": issues}


def call_groq(prompt, payload, model, key):
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
    r = client.chat.completions.create(model=model, temperature=0, response_format={"type": "json_object"},
                                       messages=[{"role": "system", "content": prompt},
                                                 {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
    return r.choices[0].message.content


def call_gemini(prompt, payload, model, key):
    body = {"contents": [{"parts": [{"text": prompt + "\n\n" + json.dumps(payload, ensure_ascii=False)}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model,
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    return d["candidates"][0]["content"]["parts"][0]["text"]


def review(ledger, call, model):
    """call(prompt, payload, model) -> reply text. Returns the report dict."""
    out = {"model": model, "reviewed_at": time.strftime("%Y-%m-%d %H:%M"), "problems": {}}
    for m in ledger.get("modules", []):
        for p in m.get("problems", []):
            try:
                out["problems"][p["id"]] = parse_reply(call(PROMPT, build_payload(p), model))
            except Exception as ex:  # a failed call is recorded, never silently skipped
                out["problems"][p["id"]] = {"verdict": "error", "issues": [{"where": "call", "problem": str(ex)[:200], "suggestion": "re-run"}]}
    return out


def main(argv):
    if not argv or argv[0].startswith("-"):
        print("usage: review_explanations.py <course_dir> [--engine groq|gemini] [--model NAME]")
        return 2
    course = argv[0]
    engine = argv[argv.index("--engine") + 1] if "--engine" in argv else "groq"
    model = argv[argv.index("--model") + 1] if "--model" in argv else ("openai/gpt-oss-120b" if engine == "groq" else "gemini-flash-latest")
    keyname = "GROQ_API_KEY" if engine == "groq" else "GEMINI_API_KEY"
    key = os.environ.get(keyname)
    if not key:
        print("%s is not set (name only is checked; never paste a key in chat)" % keyname)
        return 1
    with open(os.path.join(course, "course_curriculum_ledger.json"), encoding="utf-8") as f:
        ledger = json.load(f)
    fn = call_groq if engine == "groq" else call_gemini
    rep = review(ledger, lambda pr, pl, md: fn(pr, pl, md, key), model)
    rep["engine"] = engine
    rp = os.path.join(course, "_audit", "review_resolutions.json")  # {problem id: why the remaining issues are not errors}
    if os.path.isfile(rp):
        with open(rp, encoding="utf-8") as f:
            for pid, why in json.load(f).items():
                if pid in rep["problems"] and rep["problems"][pid]["verdict"] == "issues":
                    rep["problems"][pid].update(verdict="resolved", resolution=why)
    os.makedirs(os.path.join(course, "_audit"), exist_ok=True)
    with open(os.path.join(course, "_audit", "explanation_review.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    bad = {k: v for k, v in rep["problems"].items() if v["verdict"] not in ("ok", "resolved")}
    print("reviewed %d problems with %s: %d ok, %d need attention -> _audit/explanation_review.json" % (len(rep["problems"]), model, len(rep["problems"]) - len(bad), len(bad)))
    for k, v in bad.items():
        for i in v["issues"]:
            print("  %s | %s | %s" % (k, str(i.get("where"))[:50], str(i.get("problem"))[:110]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
