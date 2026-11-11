"""Transcribe course media to timestamped transcripts.

Usage: python transcribe.py <course_dir> [--provider groq|local] [--only <audio_basename>]

- Providers: 'groq' (OpenAI-compatible Whisper large-v3 via the GROQ_API_KEY env var; audio is sent to
  Groq - user approved this for lecture audio on 2026-11-10) or 'local' (faster-whisper on CPU).
- Default chain: groq, then local if groq fails for a chunk-set.
- Language is NOT forced: lectures mix Egyptian Arabic and English technical terms.
- The glossary (course glossary.txt) is passed as the decoding prompt so terms like "amplifier" survive.
- API keys come only from environment variables; nothing is written to disk.
Output per media: <transcript>.jsonl and the '[start -> end] text' .txt named in course.json.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

CHUNK_SECONDS = 600
GROQ_BASE = "https://api.groq.com/openai/v1"
GROQ_MODEL = "whisper-large-v3"


def extract_audio(video, out_mp3):
    os.makedirs(os.path.dirname(out_mp3), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-i", video, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", out_mp3],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def split_audio(mp3, tmpdir):
    pattern = os.path.join(tmpdir, "chunk_%03d.mp3")
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-i", mp3, "-f", "segment", "-segment_time", str(CHUNK_SECONDS),
                    "-c", "copy", pattern], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return sorted(os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.startswith("chunk_"))


def glossary_prompt(course, cfg):
    path = os.path.join(course, cfg.get("glossary", "glossary.txt"))
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as f:
        terms = [ln.strip() for ln in f if ln.strip()]
    # Whisper prompts are limited (~224 tokens): keep it short or the API rejects the request.
    return ("Arabic lecture, English terms: " + ", ".join(terms))[:380]


def groq_segments(chunk, prompt, offset):
    from openai import OpenAI
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")
    client = OpenAI(api_key=key, base_url=GROQ_BASE)
    last = None
    for attempt in range(4):
        try:
            with open(chunk, "rb") as f:
                r = client.audio.transcriptions.create(model=GROQ_MODEL, file=f, response_format="verbose_json",
                                                       prompt=prompt or None, temperature=0)
            segs = getattr(r, "segments", None) or r.model_dump().get("segments", [])
            out = []
            for s in segs:
                g = (lambda k: s[k]) if isinstance(s, dict) else (lambda k: getattr(s, k))
                out.append((offset + float(g("start")), offset + float(g("end")), g("text").strip()))
            return out
        except Exception as exc:  # noqa: BLE001 - retry on rate limits / transient errors
            last = exc
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("groq failed after retries: %r" % last)


def local_segments(mp3, prompt):
    import faster_whisper
    model = faster_whisper.WhisperModel("medium", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(mp3, beam_size=5, initial_prompt=prompt or None)  # language auto
    return [(s.start, s.end, s.text.strip()) for s in segs]


def write_outputs(course, item, segs):
    txt = os.path.join(course, item["transcript"])
    os.makedirs(os.path.dirname(txt), exist_ok=True)
    with open(txt, "w", encoding="utf-8") as f:
        for a, b, t in segs:
            f.write("[%.2f -> %.2f] %s\n" % (a, b, t))
    with open(os.path.splitext(txt)[0] + ".jsonl", "w", encoding="utf-8") as f:
        for a, b, t in segs:
            f.write(json.dumps({"start": a, "end": b, "text": t}, ensure_ascii=False) + "\n")


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    course = argv[0]
    provider = argv[argv.index("--provider") + 1] if "--provider" in argv else "groq"
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    with open(os.path.join(course, "course.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    prompt = glossary_prompt(course, cfg)
    for item in cfg["media"]:
        if only and os.path.basename(item["audio"]) != only:
            continue
        audio = os.path.join(course, item["audio"])
        if not (os.path.isfile(audio) and os.path.getsize(audio) > 0):
            extract_audio(os.path.join(cfg["root"], item["video"]), audio)
        segs = None
        if provider == "groq":
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    segs = []
                    for i, ch in enumerate(split_audio(audio, tmp)):
                        segs += groq_segments(ch, prompt, i * CHUNK_SECONDS)
            except Exception as exc:  # noqa: BLE001
                print("groq failed for %s: %r -> falling back to local" % (item["audio"], exc))
                segs = None
        if segs is None:
            segs = local_segments(audio, prompt)
        write_outputs(course, item, segs)
        print("OK %s: %d segments, last end %.0fs" % (item["transcript"], len(segs), segs[-1][1] if segs else 0))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
