"""Question pool expansion pipeline.

    python3 tools/qgen/qgen.py plan AIB-C01            # gaps per domain / task statement, multi-answer quota
    python3 tools/qgen/qgen.py check tools/qgen/batches/AIB-C01/b01.txt   # validate only
    python3 tools/qgen/qgen.py ingest tools/qgen/batches/AIB-C01/b01.txt  # validate + write data/*.json
    python3 tools/qgen/qgen.py report                  # all exams vs target

Batch source format (one block per question, blocks start with '@'):
    @ AIB-C01 D2 T2.2 advanced use-case [+SOA-C03:D3 ...]
    S: stem text (for multi-answer end with "(Select TWO)")
    A: choice text
    B: choice text
    C: choice text
    D: choice text
    E: optional fifth choice (multi-answer questions use 5)
    K: B            or  K: A,C
    W: why the correct answer is right (one or two sentences)
    X: A=why A is wrong | C=why C is wrong | D=why D is wrong      (one entry per wrong choice)
    T: key takeaway
    V: Amazon Bedrock, AWS Lambda            (services, optional)
    I: Q002201                               (optional: keep this id after rewriting the stem)

Ingest is idempotent: each block is identified by a hash of its stem, so re-ingesting an edited batch
updates the same question id instead of adding a duplicate. Choices are re-ordered so correct-answer
positions stay balanced per exam, and the batch is rejected on schema errors, near-duplicates, or
a correct answer that is conspicuously the longest option too often.
"""
import collections, hashlib, json, pathlib, random, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
STATE = ROOT / "tools/qgen/ingested.json"          # block hash -> question id
SPECS = json.loads((DATA / "exam-specs.json").read_text())
TASKS = json.loads((ROOT / "tools/qgen/tasks.json").read_text())
EXAMS = [k for k in SPECS if not k.startswith("_")]
TARGET_MULT = 5                                   # pool target = 5 full exams
DIFFS = {"applied", "advanced"}
SCEN = {"use-case", "troubleshooting", "definition", "comparison", "tradeoff"}
NUM_WORD = {2: "TWO", 3: "THREE"}


def load_exam(code):
    return json.loads((DATA / f"{code}.json").read_text())


def save_exam(code, qs):
    (DATA / f"{code}.json").write_text(json.dumps(qs, indent=1, ensure_ascii=False) + "\n")


def domain_map():
    p = DATA / "exam-domains.json"
    return json.loads(p.read_text()) if p.exists() else {}


def domain_of(q, exam, dmap):
    if q["examCodes"][0] == exam:
        return q["domainCode"]
    return dmap.get(q["id"], {}).get(exam, q["domainCode"])


def target(code):
    return SPECS[code]["questions"] * TARGET_MULT


# ---------------------------------------------------------------- plan
def plan(code, quiet=False):
    qs = load_exam(code)
    dmap = domain_map()
    spec = SPECS[code]
    tgt = target(code)
    by_dom = collections.Counter(domain_of(q, code, dmap) for q in qs)
    by_task = collections.Counter(q.get("taskId") for q in qs if q["examCodes"][0] == code)
    multi = sum(1 for q in qs if len(q["correctKeys"]) > 1)
    rows = []
    for d in spec["domains"]:
        want = round(tgt * d["weight"] / 100)
        have = by_dom.get(d["code"], 0)
        dnum = d["code"][1:]
        tasks = {k: v for k, v in TASKS[code].items() if k.split(".")[0] == dnum}
        rows.append((d, want, have, tasks))
    if not quiet:
        print(f"{code}: pool {len(qs)} -> target {tgt} (need {max(0, tgt - len(qs))}); multi-answer {multi} "
              f"({multi * 100 // max(1, len(qs))}%), aim 15-20% of new questions")
        for d, want, have, tasks in rows:
            print(f"  {d['code']} {d['name']}: {have}/{want}  need {max(0, want - have)}")
            for t, name in tasks.items():
                print(f"      T{t} {name}: {by_task.get('T' + t, 0)}")
    return rows


# ---------------------------------------------------------------- parse
HEAD = re.compile(r"^@\s*(\S+)\s+(D\d)\s+(T\d\.\d)\s+(\S+)\s+(\S+)\s*(.*)$")


def parse(path):
    text = pathlib.Path(path).read_text()
    blocks, cur = [], None
    for ln, line in enumerate(text.splitlines(), 1):
        if line.startswith("@"):
            cur = {"_line": ln, "_head": line, "fields": {}}
            blocks.append(cur)
            continue
        if cur is None or not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Z]):\s?(.*)$", line)
        if m:
            cur["fields"][m.group(1)] = m.group(2).strip()
            cur["_last"] = m.group(1)
        elif cur.get("_last"):                       # continuation line
            cur["fields"][cur["_last"]] += " " + line.strip()
    return blocks


def build(block, errors):
    h = HEAD.match(block["_head"])
    where = f"line {block['_line']}"
    if not h:
        errors.append(f"{where}: bad header {block['_head']!r}")
        return None
    exam, dom, task, diff, scen, extra = h.groups()
    f = block["fields"]
    if exam not in SPECS:
        errors.append(f"{where}: unknown exam {exam}")
        return None
    if not any(d["code"] == dom for d in SPECS[exam]["domains"]):
        errors.append(f"{where}: {exam} has no {dom}")
    if task[1] != dom[1]:
        errors.append(f"{where}: task {task} is not in {dom}")
    if diff not in DIFFS:
        errors.append(f"{where}: difficulty must be one of {sorted(DIFFS)}")
    if scen not in SCEN:
        errors.append(f"{where}: scenarioType must be one of {sorted(SCEN)}")
    shared = {}
    for tok in extra.split():
        m = re.match(r"^\+(\S+):(D\d)$", tok)
        if not m or m.group(1) not in SPECS:
            errors.append(f"{where}: bad shared tag {tok!r} (use +SOA-C03:D2)")
        else:
            shared[m.group(1)] = m.group(2)
    letters = [k for k in "ABCDE" if k in f]
    if letters not in (list("ABCD"), list("ABCDE")):
        errors.append(f"{where}: choices must be A-D or A-E, got {letters}")
    for k in ("S", "K", "W", "X", "T"):
        if not f.get(k):
            errors.append(f"{where}: missing {k}:")
    if errors and any(e.startswith(where) for e in errors):
        return None
    keys = [k.strip() for k in f["K"].split(",")]
    if any(k not in letters for k in keys) or len(set(keys)) != len(keys):
        errors.append(f"{where}: bad K: {f['K']}")
        return None
    multi = len(keys) > 1
    if multi:
        want = f"(Select {NUM_WORD.get(len(keys), len(keys))})"
        if not f["S"].endswith(want):
            errors.append(f"{where}: multi-answer stem must end with {want}")
        if len(letters) != 5:
            errors.append(f"{where}: multi-answer questions use 5 choices")
    elif len(letters) != 4:
        errors.append(f"{where}: single-answer questions use 4 choices")
    texts = [f[k] for k in letters]
    if len(set(t.lower() for t in texts)) != len(texts):
        errors.append(f"{where}: duplicate choice text")
    wrong = {}
    for part in f["X"].split("|"):
        m = re.match(r"^\s*([A-E])\s*=\s*(.+)$", part)
        if m:
            wrong[m.group(1)] = m.group(2).strip()
    missing = [k for k in letters if k not in keys and k not in wrong]
    if missing:
        errors.append(f"{where}: X: has no reason for wrong choice(s) {missing}")
    if len(f["S"]) < 60:
        errors.append(f"{where}: stem too short to be a scenario")
    return {
        "exam": exam, "dom": dom, "task": task, "diff": diff, "scen": scen, "shared": shared,
        "stem": f["S"], "choices": {k: f[k] for k in letters}, "keys": keys, "why": f["W"],
        "wrong": wrong, "take": f["T"], "services": [s.strip() for s in f.get("V", "").split(",") if s.strip()],
        "pin": f.get("I") or None,
        "hash": hashlib.sha1(re.sub(r"\s+", " ", f["S"].lower()).encode()).hexdigest()[:12], "where": where,
    }


def short_label(text):
    t = re.sub(r"\s+", " ", text).strip().rstrip(".")
    return t if len(t) <= 48 else t[:45].rsplit(" ", 1)[0] + "…"


def explanation(item, order):
    lines = ["Why this is correct:", item["why"], "", "Why the other options are wrong:"]
    for k in order:
        if k not in item["keys"]:
            lines.append(f"• {short_label(item['choices'][k])}: {item['wrong'][k]}")
    lines += ["", f"Key takeaway: {item['take']}"]
    return "\n".join(lines)


# ---------------------------------------------------------------- similarity
def _tok(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def vectors(texts):
    df = collections.Counter()
    toks = []
    for t in texts:
        w = _tok(t)
        grams = set(w) | {a + "_" + b for a, b in zip(w, w[1:])}
        toks.append(grams)
        df.update(grams)
    n = len(texts)
    import math
    out = []
    for g in toks:
        v = {x: math.log((n + 1) / (df[x] + 1)) + 1 for x in g}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        out.append({k: x / norm for k, x in v.items()})
    return out


def cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0) for k, v in a.items())


def qtext(stem, correct_texts):
    return stem + " " + " ".join(correct_texts)


# ---------------------------------------------------------------- check / ingest
def check(path, write=False):
    blocks = parse(path)
    errors, warns = [], []
    items = [b for b in (build(b, errors) for b in blocks) if b]
    if not blocks:
        errors.append("no question blocks found")
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    seen_hash = collections.Counter(i["hash"] for i in items)
    for i in items:
        if seen_hash[i["hash"]] > 1:
            errors.append(f"{i['where']}: duplicate stem inside batch")

    # near-duplicate check against every existing question of the same exams (excluding own earlier ingest)
    exams = sorted({i["exam"] for i in items} | {e for i in items for e in i["shared"]})
    existing = {}
    for e in exams:
        for q in load_exam(e):
            existing[q["id"]] = q
    own_ids = {state[i["hash"]] for i in items if i["hash"] in state} | {i["pin"] for i in items if i["pin"]}
    ex_list = [q for qid, q in existing.items() if qid not in own_ids]
    ex_texts = [qtext(q["stem"], [c["text"] for c in q["choices"] if c["key"] in q["correctKeys"]]) for q in ex_list]
    new_texts = [qtext(i["stem"], [i["choices"][k] for k in i["keys"]]) for i in items]
    vecs = vectors(ex_texts + new_texts)
    ev, nv = vecs[: len(ex_texts)], vecs[len(ex_texts):]
    for idx, (i, v) in enumerate(zip(items, nv)):
        best, bq = 0, None
        for q, w in zip(ex_list, ev):
            s = cos(v, w)
            if s > best:
                best, bq = s, q
        for j in range(idx):
            s = cos(v, nv[j])
            if s > best:
                best, bq = s, {"id": f"batch {items[j]['where']}", "stem": items[j]["stem"]}
        if best >= 0.72:
            errors.append(f"{i['where']}: near-duplicate of {bq['id']} (cos {best:.2f}): {bq['stem'][:90]}")
        elif best >= 0.55:
            warns.append(f"{i['where']}: similar to {bq['id']} (cos {best:.2f})")

    # length bias: correct answer conspicuously longest
    longest = 0
    for i in items:
        lens = {k: len(t) for k, t in i["choices"].items()}
        wrong_max = max(l for k, l in lens.items() if k not in i["keys"])
        cmin = min(lens[k] for k in i["keys"])
        if cmin > wrong_max * 1.25:
            longest += 1
            warns.append(f"{i['where']}: correct answer is much longer than every distractor")
    if items and longest / len(items) > 0.25:
        errors.append(f"length bias: correct answer is clearly longest in {longest}/{len(items)} questions (max 25%)")
    def stands_out(i, longest):
        """correct answer is the longest (or shortest) option by a visible margin (8%), not a near-tie"""
        lens = {k: len(t) for k, t in i["choices"].items()}
        wrong = [l for k, l in lens.items() if k not in i["keys"]]
        if longest:
            return min(lens[k] for k in i["keys"]) > max(wrong) * 1.08
        return max(lens[k] for k in i["keys"]) < min(wrong) * 0.92
    strict = sum(1 for i in items if stands_out(i, True))
    # single-answer baseline is 25% (1 of 4); multi-answer questions raise it, so allow some headroom
    limit = 0.25 + 0.3 * sum(1 for i in items if len(i["keys"]) > 1) / max(1, len(items))
    if items and strict / len(items) > limit:
        errors.append(f"length bias: correct answer is clearly the longest option in {strict}/{len(items)} questions (limit {limit:.0%})")
    elif items:
        print(f"  correct answer clearly longest in {strict}/{len(items)} ({strict / len(items):.0%}, limit {limit:.0%})")
    singles = [i for i in items if len(i["keys"]) == 1]
    short = sum(1 for i in singles if stands_out(i, False))
    if singles and short / len(singles) > 0.30:
        errors.append(f"length bias: correct answer is clearly the shortest option in {short}/{len(singles)} single-answer questions (max 30%)")
    for i in singles:
        lens = {k: len(t) for k, t in i["choices"].items()}
        c = lens[i["keys"][0]]
        if c * 2 < min(l for k, l in lens.items() if k not in i["keys"]):
            warns.append(f"{i['where']}: correct answer is less than half the length of every distractor")

    multi = sum(1 for i in items if len(i["keys"]) > 1)
    print(f"{path}: {len(items)} questions, {multi} multi-answer, {len(errors)} errors, {len(warns)} warnings")
    for e in errors:
        print("  ERROR", e)
    for w in warns:
        print("  warn ", w)
    if errors or not write:
        return not errors
    ingest(items, state)
    return True


def place(i, letters, n, pos, rng):
    """Put the correct answer(s) in the least-used positions for this exam; shuffle the distractors."""
    slots = sorted(range(n), key=lambda p: (pos[i["exam"]]["ABCDE"[p]], rng.random()))[: len(i["keys"])]
    wrongs = [k for k in letters if k not in i["keys"]]
    rng.shuffle(wrongs)
    corrects = list(i["keys"])
    rng.shuffle(corrects)
    layout = [None] * n
    for s_, k in zip(sorted(slots), corrects):
        layout[s_] = k
    it = iter(wrongs)
    layout = [k if k else next(it) for k in layout]
    return layout, {old: "ABCDE"[p] for p, old in enumerate(layout)}


def ingest(items, state):
    rng = random.Random()
    all_ids = [q["id"] for e in EXAMS for q in load_exam(e)]
    next_num = max(int(i[1:]) for i in all_ids) + 1
    files = {e: load_exam(e) for e in EXAMS}
    dmap = domain_map()
    # current answer-position counts per exam (for balancing)
    pos = {e: collections.Counter(k for q in files[e] for k in q["correctKeys"]) for e in EXAMS}
    added = updated = 0
    existing = {q["id"]: q for e in EXAMS for q in files[e]}
    for i in items:
        letters = list(i["choices"])
        n = len(letters)
        if i["pin"]:
            state[i["hash"]] = i["pin"]           # I: Qxxxxxx keeps the id when a stem is rewritten
        prev = existing.get(state.get(i["hash"]))
        if prev and sorted(c["text"] for c in prev["choices"]) == sorted(i["choices"].values()) and \
                sorted(c["text"] for c in prev["choices"] if c["key"] in prev["correctKeys"]) == sorted(i["choices"][k] for k in i["keys"]):
            # unchanged choices: keep the published order so re-ingesting an edited batch is stable
            by_text = {t: k for k, t in i["choices"].items()}
            layout = [by_text[c["text"]] for c in prev["choices"]]
            newkey = {old: "ABCDE"[p] for p, old in enumerate(layout)}
        else:
            layout = None
        if layout is None:
            layout, newkey = place(i, letters, n, pos, rng)
        choices = [{"key": "ABCDE"[p], "text": i["choices"][old]} for p, old in enumerate(layout)]
        correct = sorted(newkey[k] for k in i["keys"])
        if not prev:
            for k in correct:
                pos[i["exam"]][k] += 1
        qid = state.get(i["hash"])
        is_new = qid is None
        if is_new:
            qid = f"Q{next_num:06d}"
            next_num += 1
        exam_codes = [i["exam"]] + sorted(i["shared"])
        q = {
            "stem": i["stem"], "choices": choices, "correctKeys": correct,
            "explanation": explanation(i, layout), "difficulty": i["diff"], "scenarioType": i["scen"],
            "services": i["services"], "taskId": i["task"], "domainCode": i["dom"], "examCodes": exam_codes, "id": qid,
        }
        for e in EXAMS:
            lst = files[e]
            idx = next((n_ for n_, x in enumerate(lst) if x["id"] == qid), None)
            if e in exam_codes:
                if idx is None:
                    lst.append(q)
                else:
                    lst[idx] = q
            elif idx is not None:                   # exam removed from an edited block
                lst.pop(idx)
        dmap.pop(qid, None)
        if i["shared"]:
            dmap[qid] = dict(i["shared"])
        state[i["hash"]] = qid
        added += is_new
        updated += not is_new
    for e in EXAMS:
        files[e].sort(key=lambda x: x["id"])
        save_exam(e, files[e])
    (DATA / "exam-domains.json").write_text(json.dumps(dict(sorted(dmap.items())), indent=1) + "\n")
    STATE.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
    print(f"ingested: {added} new, {updated} updated")


def report():
    dmap = domain_map()
    print(f"{'exam':9} {'pool':>5} {'target':>6} {'need':>5} {'multi%':>6}  answer positions   correct-clearly-longest%")
    for e in EXAMS:
        qs = load_exam(e)
        multi = sum(1 for q in qs if len(q["correctKeys"]) > 1)
        pos = collections.Counter(k for q in qs for k in q["correctKeys"])
        longest = 0
        for q in qs:
            lens = {c["key"]: len(c["text"]) for c in q["choices"]}
            wrong = [l for k, l in lens.items() if k not in q["correctKeys"]]
            if min(lens[k] for k in q["correctKeys"]) > max(wrong) * 1.08:   # clearly longest, ignoring near-ties
                longest += 1
        print(f"{e:9} {len(qs):5} {target(e):6} {max(0, target(e) - len(qs)):5} {multi * 100 / len(qs):6.1f}  "
              f"{' '.join(f'{k}{pos[k]}' for k in 'ABCDE')}   {longest * 100 / len(qs):.0f}%")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "plan":
        for e in (sys.argv[2:] or EXAMS):
            plan(e)
    elif cmd in ("check", "ingest"):
        ok = all(check(p, write=(cmd == "ingest")) for p in sys.argv[2:])
        sys.exit(0 if ok else 1)
    else:
        report()
