"""Build glossary.txt candidates from course PDFs (slides). Usage: build_glossary.py <course_dir> [--top 60]
Counts English 1-3 word terms in the slide text and writes glossary.txt (most frequent first)."""
import collections, json, os, re, sys, warnings
warnings.filterwarnings("ignore")
import fitz

STOP = set("the a an of and or to in is are for with on by as at be this that it from we can if then so not will has have its into which when where than these those one two use used using also all any each such per via but their there they our out more most only other".split())

def main():
    course = sys.argv[1]
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 60
    cfg = json.load(open(os.path.join(course, "course.json"), encoding="utf-8"))
    root = cfg["root"]
    cnt = collections.Counter()
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith(".pdf"):
                try:
                    doc = fitz.open(os.path.join(dp, f))
                except Exception:
                    continue
                for page in doc:
                    words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", page.get_text()) ]
                    low = [w.lower() for w in words]
                    for n in (1, 2, 3):
                        for i in range(len(low) - n + 1):
                            g = low[i:i + n]
                            if g[0] in STOP or g[-1] in STOP or any(x in STOP for x in g[1:-1]):
                                continue
                            cnt[" ".join(g)] += 1
    terms = [t for t, c in cnt.most_common(400) if c >= 3]
    # drop unigrams already covered by a more frequent bigram containing them
    out = terms[:top]
    with open(os.path.join(course, "glossary_candidates.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join("%s\t%d" % (t, cnt[t]) for t in terms))
    print(len(terms), "candidates ->", os.path.join(course, "glossary_candidates.txt"))

if __name__ == "__main__":
    main()
