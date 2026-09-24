"""Randomize answer positions for questions whose correct answers cluster on A/B.
Deterministic per question id, so every exam file that shares a question gets the same order.
Letter references in explanations ("Option B", "(A, D)", "C is wrong", ...) are remapped to the new positions.
Usage: python3 tools/rebalance_answers.py [--before Q001953]
"""
import json, glob, random, re, sys, collections
BEFORE = sys.argv[sys.argv.index("--before")+1] if "--before" in sys.argv else "Q001953"
EXCL = r"(?:account|accounts|vpc|vpcs|region|regions|connection|connections|site|sites|zone|tier|type|class|plan|grade|team|teams|service|services|server|servers|app|application|bucket|subnet|table|version|model|stage|step|phase|group|user|role|host|node|cluster|database|db|office|branch|partner|company|customer|tenant|department|stack|pipeline|environment|queue|topic|vendor|shard|endpoint|function|job|interface|record|policy|scenario|case|test|sample|variant|dataset|window|domain|ou|workload|project|product|flow|path|line|router|device|link|port|unit)"
TOK = re.compile(r"(?<![\w\-/.'’])([A-E])(?![\w\-+’'#.:%])")
VERB = re.compile(r"\s*(?:,|\)|/|and\b|or\b|nor\b|is\b|are\b|was\b|would\b|could\b|only\b|also\b|describes?\b|misses\b|confuses?\b|ignores?\b|incorrectly\b|wrongly\b|reverses?\b|stores?\b|suggests?\b|uses?\b|fails?\b|violates?\b|adds?\b|lacks?\b|requires?\b|grants?\b|does\b|do\b|doesn|isn|relies\b|misstates?\b|overstates?\b|understates?\b|mischaracterizes?\b|removes?\b|leaves?\b|introduces?\b|offers?\b|provides?\b|—|–|-\s)")
PROTECT = [(re.compile(r"\bA/B\b"), "\x00AB\x00"), (re.compile(r"\bA and B test"), "\x00AANDB\x00 test")]
def remap(text, mp):
    for rx, ph in PROTECT: text = rx.sub(ph, text)
    out, last = [], 0
    for m in TOK.finditer(text):
        ch, i = m.group(1), m.start()
        if re.search(EXCL + r"\s*$", text[max(0, i-20):i], re.I): continue
        if ch == "A":
            pre = text[:i].rstrip()
            if (pre == "" or pre[-1] in '.!?:"“') and not VERB.match(text[m.end():m.end()+25]): continue
        out += [text[last:i], mp[ch]]; last = m.end()
    out.append(text[last:]); text = "".join(out)
    return text.replace("\x00AB\x00", "A/B").replace("\x00AANDB\x00", "A and B")
def rebalance(q):
    keys = [c["key"] for c in q["choices"]]; texts = [c["text"] for c in q["choices"]]
    order = list(range(len(texts))); random.Random(q["id"]).shuffle(order)   # order[new_pos] = old_pos
    mp = {keys[old]: keys[new] for new, old in enumerate(order)}
    q["choices"] = [{"key": keys[n], "text": texts[o]} for n, o in enumerate(order)]
    q["correctKeys"] = sorted(mp[k] for k in q["correctKeys"])
    q["explanation"] = remap(q["explanation"], mp)
    return q
if __name__ == "__main__":
    files = sorted(glob.glob("data/*-*.json")); done = {}
    for f in files:
        for q in json.load(open(f)):
            if q["id"] < BEFORE and q["id"] not in done: done[q["id"]] = rebalance(dict(q))
    for f in files:
        d = [done.get(q["id"], q) for q in json.load(open(f))]
        json.dump(d, open(f, "w"), ensure_ascii=False)
    allq = {q["id"]: q for f in files for q in json.load(open(f))}
    print(len(done), "rebalanced;", collections.Counter(k for q in allq.values() for k in q["correctKeys"]))
