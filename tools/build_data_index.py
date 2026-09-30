"""Build data/exams-index.json: per-exam question counts, id ranges and a content hash per data file.

The site downloads this small file first, then fetches an exam's questions only when that exam
is opened, as data/<EXAM>.json?v=<hash>. Because the URL changes whenever the file changes,
browsers can keep the big files in their HTTP cache between visits.

Run after changing anything in data/ (qgen ingest runs it automatically).
"""
import hashlib, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EXTRA = ["exam-specs.json", "exam-domains.json"]


def id_ranges(docs):
    """Question ids (Q000123 -> 123) of one exam as [first, last] runs, so the bookmarks view can tell
    which exam files hold a bookmarked id without downloading them all."""
    nums = sorted(int(d["id"][1:]) for d in docs)
    runs = []
    for n in nums:
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    return runs


def build():
    specs = json.loads((DATA / "exam-specs.json").read_text(encoding="utf-8"))
    exams, unique, shared = {}, {}, set()
    for code in sorted(k for k in specs if not k.startswith("_")):
        path = DATA / f"{code}.json"
        if not path.exists():
            continue
        raw = path.read_bytes()
        docs = json.loads(raw)
        exams[code] = {"count": len(docs), "v": hashlib.sha1(raw).hexdigest()[:10], "ids": id_ranges(docs)}
        for d in docs:
            unique[d["id"]] = d
            if len(d.get("examCodes") or []) > 1:
                shared.add(d["id"])
    index = {
        "exams": exams,
        "files": {name: hashlib.sha1((DATA / name).read_bytes()).hexdigest()[:10] for name in EXTRA},
        "totalUnique": len(unique),
        "sharedUnique": len(shared),
    }
    out = DATA / "exams-index.json"
    text = json.dumps(index, indent=1, sort_keys=True) + "\n"
    if not out.exists() or out.read_text(encoding="utf-8") != text:
        out.write_text(text, encoding="utf-8", newline="\n")
    return index


if __name__ == "__main__":
    idx = build()
    print(f"exams-index.json: {len(idx['exams'])} exams, {idx['totalUnique']} unique questions")
