"""Build data/exams-index.json: per-exam question counts plus a content hash per data file.

The site downloads this small file first, then fetches an exam's questions only when that exam
is opened, as data/<EXAM>.json?v=<hash>. Because the URL changes whenever the file changes,
browsers can keep the big files in their HTTP cache between visits.

Run after changing anything in data/ (qgen ingest runs it automatically).
"""
import hashlib, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EXTRA = ["exam-specs.json", "exam-domains.json"]


def build():
    specs = json.loads((DATA / "exam-specs.json").read_text())
    exams, unique, shared = {}, {}, set()
    for code in sorted(k for k in specs if not k.startswith("_")):
        path = DATA / f"{code}.json"
        if not path.exists():
            continue
        raw = path.read_bytes()
        docs = json.loads(raw)
        exams[code] = {"count": len(docs), "v": hashlib.sha1(raw).hexdigest()[:10]}
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
    if not out.exists() or out.read_text() != text:
        out.write_text(text)
    return index


if __name__ == "__main__":
    idx = build()
    print(f"exams-index.json: {len(idx['exams'])} exams, {idx['totalUnique']} unique questions")
