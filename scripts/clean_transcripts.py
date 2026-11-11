"""Remove known ASR hallucination lines (Whisper invents subtitles in silence). Usage: clean_transcripts.py <course_dir>
Every removed segment is logged to _audit/dropped_segments.json; originals kept as *.orig."""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gates


def main():
    course = sys.argv[1]
    cfg = gates.jload(os.path.join(course, "course.json"))
    dropped = []
    for item in cfg.get("media", []):
        for key in ("transcript", "transcript_jsonl"):
            rel = item.get(key) or (item["transcript"].replace(".txt", ".jsonl") if key == "transcript_jsonl" else None)
            if not rel:
                continue
            path = os.path.join(course, rel)
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
            keep = []
            for ln in lines:
                if any(h.lower() in ln.lower() for h in gates.ASR_HALLUCINATIONS):
                    dropped.append({"file": rel, "line": ln})
                else:
                    keep.append(ln)
            if len(keep) != len(lines):
                if not os.path.exists(path + ".orig"):
                    shutil.copy2(path, path + ".orig")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(keep) + "\n")
    os.makedirs(os.path.join(course, "_audit"), exist_ok=True)
    with open(os.path.join(course, "_audit", "dropped_segments.json"), "w", encoding="utf-8") as f:
        json.dump(dropped, f, ensure_ascii=False, indent=1)
    print("dropped %d hallucinated lines" % len(dropped))


if __name__ == "__main__":
    main()
