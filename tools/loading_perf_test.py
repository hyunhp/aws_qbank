"""Loading and reveal-smoothness checks (Playwright, local server, mobile viewport).

- First visit downloads only data/exams-index.json and the one exam being shown.
- Exam files are requested with a ?v=<hash> that matches data/exams-index.json.
- Opening Bookmarks loads only the exams holding bookmarked ids (id ranges in exams-index.json).
- Explanations are fetched once per exam (data/explanations/<EXAM>.json?v=<e>), prefetched when idle.
- Revealing explanations stays smooth on a 4x-throttled CPU (no long frames).
    python3 tools/loading_perf_test.py
"""
import functools, http.server, json, pathlib, re, sys, threading
from playwright.sync_api import sync_playwright

ROOT = str(pathlib.Path(__file__).resolve().parents[1])
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/"
index = json.load(open(pathlib.Path(ROOT, "data", "exams-index.json")))
diag_ids = set(json.load(open(pathlib.Path(ROOT, "diagrams", "index.json")))["ids"])
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    if cond: ok += 1
    else: fail += 1; print("FAIL", name, info)

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    data_reqs = []
    pg.on("request", lambda r: data_reqs.append(r.url) if "/data/" in r.url else None)
    pg.goto(BASE + "#exam=SAA-C03"); pg.wait_for_selector(".qcard"); pg.wait_for_timeout(800)
    exam_files = [u for u in data_reqs if re.search(r"/data/[A-Z]{3}-C\d{2}\.json", u)]
    check("first visit loads one exam file", len(exam_files) == 1 and "SAA-C03" in exam_files[0], exam_files)
    check("index loaded", any("exams-index.json" in u for u in data_reqs), data_reqs)
    check("versioned exam URL", exam_files and exam_files[0].endswith("?v=" + index["exams"]["SAA-C03"]["v"]), exam_files)
    check("stats from index", pg.inner_text("#statTotal").strip() == str(index["totalUnique"]), pg.inner_text("#statTotal"))
    check("chip counts from index", str(index["exams"]["AIF-C01"]["count"]) in pg.inner_text("#chipRow"))

    # bookmark something from another exam, then open Bookmarks in a fresh page
    aif = json.load(open(pathlib.Path(ROOT, "data", "AIF-C01.json"), encoding="utf-8"))[0]["id"]
    pg.evaluate(f"localStorage.setItem('aws_qbank_bookmarks_v1', JSON.stringify(['{aif}']))")
    pg2 = ctx.new_page(); reqs2 = []
    pg2.on("request", lambda r: reqs2.append(r.url) if "/data/" in r.url else None)
    pg2.goto(BASE + "#bookmarks"); pg2.wait_for_selector(".qcard", timeout=15000)
    check("bookmark from other exam shown", pg2.query_selector(f"#card-{aif}") is not None)
    loaded = sorted(re.search(r"/data/([A-Z]{3}-C\d{2})\.json", u).group(1) for u in reqs2 if re.search(r"/data/[A-Z]{3}-C\d{2}\.json", u))
    holders = sorted(c for c, e in index["exams"].items() if any(a <= int(aif[1:]) <= b for a, b in e["ids"]))
    check("bookmarks view loads only the exams holding bookmarked ids", loaded == holders and len(loaded) < len(index["exams"]), (loaded, holders))
    pg2.close()

    # reveal smoothness under CPU throttling
    cdp = pg.context.new_cdp_session(pg); cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    pg.evaluate("""window.__f=[];(function f(t){__f.push(t);requestAnimationFrame(f)})(performance.now());""")
    ids = pg.eval_on_selector_all(".qcard", "els => els.map(e => e.dataset.qid)")
    sample = [i for i in ids if i in diag_ids][:3] + [i for i in ids if i not in diag_ids][:3]
    pg.wait_for_timeout(2500)  # let idle warm-up finish
    worst = []
    for qid in sample:
        pg.evaluate(f"document.getElementById('card-{qid}').scrollIntoView({{block:'center'}})"); pg.wait_for_timeout(300)
        t0 = pg.evaluate("performance.now()")
        pg.click(f"#card-{qid} .reveal-link"); pg.wait_for_timeout(1800)
        w = pg.evaluate("(t0)=>{const f=__f.filter(x=>x>t0);let m=0;for(let i=1;i<f.length;i++)m=Math.max(m,f[i]-f[i-1]);return Math.round(m)}", t0)
        worst.append(w)
        check(f"explanation visible {qid}", pg.is_visible(f"#explain-{qid}"))
    check("no long frames on reveal (4x CPU)", max(worst) <= 100, worst)
    exp_reqs = [u for u in data_reqs if "/data/explanations/" in u]
    check("explanations fetched once, versioned, only for the open exam",
          len(exp_reqs) == 1 and exp_reqs[0].endswith("SAA-C03.json?v=" + index["exams"]["SAA-C03"]["e"]), exp_reqs)
    check("exam file carries no explanations", "explanation" not in json.load(open(pathlib.Path(ROOT, "data", "SAA-C03.json"), encoding="utf-8"))[0])
    b.close()
srv.shutdown()
print(f"{ok}/{ok+fail} passed"); sys.exit(1 if fail else 0)
