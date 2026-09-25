"""Site test: in every exam view, answer one question with its own diagram and one shared question,
and check the diagram renders with no page errors and no horizontal overflow at 390 px.
    python3 tools/diagrams/site_test.py
"""
import functools, http.server, threading, json, glob
from playwright.sync_api import sync_playwright
import pathlib
ROOT=str(pathlib.Path(__file__).resolve().parents[2])
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=http.server.ThreadingHTTPServer(("127.0.0.1",0),functools.partial(Q,directory=ROOT))
threading.Thread(target=srv.serve_forever,daemon=True).start()
BASE=f"http://127.0.0.1:{srv.server_address[1]}/"
ids=set(json.load(open(f"{ROOT}/diagrams/index.json"))["ids"])
exams={}
for f in sorted(glob.glob(f"{ROOT}/data/*.json")):
    if f.endswith("_manifest.json"): continue
    code=f.split("/")[-1][:-5]
    qs=json.load(open(f))
    withd=[q["id"] for q in qs if q["id"] in ids]
    shared=[q["id"] for q in qs if q["id"] in ids and len(q["examCodes"])>1 and q["examCodes"][0]!=code]
    own=[i for i in withd if i not in shared]
    exams[code]=(own[0] if own else None, shared[0] if shared else None)
fails=[]
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={"width":390,"height":844}); pg=ctx.new_page()
    errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type=="error" and "ERR_FAILED" not in m.text else None)
    pg.route("**/fonts.googleapis.com/**",lambda r:r.abort())
    for code,(qid,sh) in exams.items():
        for target in list(dict.fromkeys(x for x in (qid,sh) if x)):
            pg.goto(BASE+f"?fresh={target}#exam={code}"); pg.wait_for_selector(".qcard")
            pg.click("#sequentialBtn"); pg.wait_for_selector(f"#card-{target}")
            rl=pg.locator(f"#card-{target} .reveal-link")
            (rl.first.click() if rl.count() else pg.locator(f"#card-{target} .choice").first.click())
            try:
                pg.wait_for_selector(f"#explain-{target} figure.qb-diagram svg .qb-edge", state="attached", timeout=8000)
                w=pg.evaluate("document.documentElement.scrollWidth")
                ok = w<=390
                print(f"{code:8} {target} {'shared' if target==sh else 'own   '} ok (page width {w})")
                if not ok: fails.append((code,target,"overflow"))
            except Exception as e:
                print(code,target,"FAIL"); fails.append((code,target,"no diagram"))
    # no-diagram question shows none
    pg.goto(BASE+"#exam=AIB-C01"); pg.wait_for_selector(".qcard"); pg.click("#sequentialBtn")
    nod=pg.evaluate(f"[...document.querySelectorAll('.qcard')].map(c=>c.dataset.qid).find(id=>!{json.dumps(sorted(ids))}.includes(id))")
    pg.locator(f"#card-{nod} .choice").first.click(); pg.wait_for_timeout(700)
    print("no-diagram question", nod, "figure count", pg.locator(f"#explain-{nod} figure").count())
    print("page errors / console errors:", errs)
    b.close()
srv.shutdown()
print("FAILS:",fails)
