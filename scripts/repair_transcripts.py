"""Re-transcribe suspicious passages (long English-only runs = ASR translated the speech) with two alternative
Groq configs and patch the transcript with the first candidate that contains Arabic.
Usage: repair_transcripts.py <course_dir>. Backups: *.pre_repair. Log: _audit/repair_log.json.
Passages no candidate can fix go to _audit/needs_human.json (a person must listen); nothing is guessed."""
import json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gates
from openai import OpenAI

AR = re.compile(r"[\u0600-\u06FF]")


def arabic_share(t):
    letters = [c for c in t if c.isalpha()]
    return sum(1 for c in letters if AR.match(c)) / len(letters) if letters else 0


def main():
    course = sys.argv[1]
    cfg = gates.jload(os.path.join(course, "course.json"))
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        print("GROQ_API_KEY is not set"); return 1
    client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
    gl = ", ".join(l.strip() for l in open(os.path.join(course, cfg.get("glossary", "glossary.txt")), encoding="utf-8") if l.strip())
    prompt = ("Arabic lecture, English terms: " + gl)[:380]
    configs = [("large-v3+ar+glossary", dict(model="whisper-large-v3", language="ar", prompt=prompt)),
               ("turbo+ar", dict(model="whisper-large-v3-turbo", language="ar"))]
    log, human = [], []
    for item in cfg["media"]:
        tpath = os.path.join(course, item["transcript"])
        segs = gates.parse_transcript(tpath)
        runs = gates.english_only_runs(segs)
        if not runs:
            continue
        patches = []
        for r in runs:
            t0, t1 = max(0.0, r[0][0] - 1), r[-1][1] + 1
            clip = os.path.join(course, "_audit", "repair_clip.mp3")
            os.makedirs(os.path.dirname(clip), exist_ok=True)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i",
                            os.path.join(course, item["audio"]), clip], check=True)
            chosen = None
            for name, kw in configs:
                with open(clip, "rb") as f:
                    out = client.audio.transcriptions.create(file=f, response_format="text", temperature=0, **kw)
                txt = (out if isinstance(out, str) else out.text).strip()
                if arabic_share(txt) >= 0.25 and not gates.has_foreign_script([(0, 0, txt)]):
                    chosen = (name, txt); break
            os.remove(clip)
            entry = {"media": item["video"], "start": r[0][0], "end": r[-1][1], "old": " ".join(x[2] for x in r)[:400]}
            if chosen:
                entry.update(engine=chosen[0], new=chosen[1][:400]); patches.append((r, chosen[1])); log.append(entry)
            else:
                human.append(entry)
        if patches:
            for ext in ("", ):
                pass
            for path in (tpath, os.path.splitext(tpath)[0] + ".jsonl"):
                if os.path.isfile(path) and not os.path.exists(path + ".pre_repair"):
                    shutil.copy2(path, path + ".pre_repair")
            rep = {id(x): (r, t) for r, t in patches for x in r[:1]}
            drop = {id(x) for r, _ in patches for x in r}
            new = []
            for s in segs:
                if id(s) in rep:
                    r, t = rep[id(s)]
                    new.append((r[0][0], r[-1][1], t))
                elif id(s) not in drop:
                    new.append(s)
            with open(tpath, "w", encoding="utf-8") as f:
                f.write("\n".join("[%.2f -> %.2f] %s" % x for x in new) + "\n")
            jp = os.path.splitext(tpath)[0] + ".jsonl"
            with open(jp, "w", encoding="utf-8") as f:
                for a, b, t in new:
                    f.write(json.dumps({"start": a, "end": b, "text": t}, ensure_ascii=False) + "\n")
    json.dump(log, open(os.path.join(course, "_audit", "repair_log.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(human, open(os.path.join(course, "_audit", "needs_human.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("repaired %d passages, %d need a human" % (len(log), len(human)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
