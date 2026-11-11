"""Second-engine spot check. Usage: cross_check.py <course_dir> [--n 12] [--engine gemini|groq-turbo] [--model NAME]
Cuts N 30 s audio windows (spread over all media), has Gemini transcribe them, and compares with the Groq
transcript on the language-neutral tokens (English words + digits). Writes _audit/spot_check.json:
 ok=true when they agree, ok=false when they disagree (a human must listen and fix 'ok' + 'heard').
Key from env GEMINI_API_KEY only. Audio is sent to Google; tell the user before running."""
import base64, json, os, re, subprocess, sys, time, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gates

WIN = 30.0
AGREE = 0.6


def tokens(text):
    t = gates.norm(text)
    return {w for w in t.split() if re.fullmatch(r"[a-z]{3,}|\d+(\.\d+)?", w)}


def gemini(audio_path, model, key):
    b64 = base64.b64encode(open(audio_path, "rb").read()).decode()
    body = {"contents": [{"parts": [
        {"text": "Transcribe this Egyptian-Arabic lecture clip verbatim. Keep English technical terms in English. Output only the transcript."},
        {"inline_data": {"mime_type": "audio/mpeg", "data": b64}}]}]}
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model,
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    return d["candidates"][0]["content"]["parts"][0]["text"]


def groq_turbo(audio_path, model, key):
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
    with open(audio_path, "rb") as f:
        r = client.audio.transcriptions.create(model=model, file=f, response_format="text", temperature=0)
    return r if isinstance(r, str) else r.text


def main():
    course = sys.argv[1]
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 12
    engine = sys.argv[sys.argv.index("--engine") + 1] if "--engine" in sys.argv else "gemini"
    default_model = "whisper-large-v3-turbo" if engine == "groq-turbo" else "gemini-flash-latest"
    model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else default_model
    keyname = "GROQ_API_KEY" if engine == "groq-turbo" else "GEMINI_API_KEY"
    key = os.environ.get(keyname)
    if not key:
        print("%s is not set" % keyname); return 1
    call = groq_turbo if engine == "groq-turbo" else gemini
    cfg = gates.jload(os.path.join(course, "course.json"))
    media = cfg["media"]
    per = max(1, -(-n // len(media)))
    entries = []
    for item in media:
        segs = gates.parse_transcript(os.path.join(course, item["transcript"]))
        dur = segs[-1][1]
        # pick windows with enough English tokens to compare, evenly spread
        cands = []
        t = 20.0
        while t + WIN < dur:
            txt = " ".join(s[2] for s in segs if s[0] >= t and s[1] <= t + WIN)
            if len(tokens(txt)) >= 4:
                cands.append((t, txt))
            t += WIN
        step = max(1, len(cands) // per)
        for t, txt in cands[::step][:per]:
            clip = os.path.join(course, "_audit", "clip_%d.mp3" % len(entries))
            os.makedirs(os.path.dirname(clip), exist_ok=True)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-t", str(WIN), "-i",
                            os.path.join(course, item["audio"]), clip], check=True)
            other, last = None, None
            for attempt in range(4):
                try:
                    other = call(clip, model, key)
                    break
                except urllib.error.HTTPError as exc:
                    last = "HTTP %s" % exc.code
                    time.sleep(8 * (attempt + 1))
                except Exception as exc:
                    last = type(exc).__name__
                    time.sleep(8 * (attempt + 1))
            if os.path.exists(clip): os.remove(clip)
            if other is None:
                print("gemini failed at %s %ss: %s (after retries)" % (item["video"], t, last)); return 1
            a, b = tokens(txt), tokens(other)
            score = len(a & b) / len(a) if a else 0.0
            entries.append({"media": item["video"], "t": t, "ok": score >= AGREE, "agreement": round(score, 2),
                            "groq": txt[:300], "second_engine": other[:300], "checker": engine + ":" + model})
            print("%s @%ds agreement %.2f" % (item["video"].split("/")[-1], t, score))
    out = os.path.join(course, "_audit", "spot_check.json")
    json.dump({"entries": entries}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    bad = [e for e in entries if not e["ok"]]
    print("%d windows, %d disagree -> %s" % (len(entries), len(bad), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
