"""End-to-end tests for mock exam mode (Playwright, local server).
    python3 tools/mock_e2e_test.py
"""
import functools, http.server, threading, sys, json, pathlib, time
from playwright.sync_api import sync_playwright
ROOT = str(pathlib.Path(__file__).resolve().parents[1])
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/"
data = {p.stem: {q["id"]: q for q in json.load(open(p))} for p in pathlib.Path(ROOT, "data").glob("*.json") if not p.stem.startswith("_") and not p.stem.startswith("exam-")}
res = []
def ok(n, c, info=""): res.append((n, bool(c))); print(("PASS " if c else "FAIL ") + n + (f"  [{info}]" if info and not c else ""))

def state(pg): return pg.evaluate("JSON.parse(localStorage.getItem('aws_qbank_mock_active_v1')||'null')")

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    pg.goto(BASE + "#exam=SAA-C03"); pg.wait_for_selector(".qcard")
    pg.click("#mockBtn"); pg.wait_for_selector(".mk h2")
    ok("setup opens for current exam", pg.eval_on_selector("#mkExam", "e=>e.value") == "SAA-C03")
    ok("url is #mock=SAA-C03", pg.evaluate("location.hash") == "#mock=SAA-C03")
    ok("question bank hidden", pg.evaluate("document.querySelector('.wrap').hidden"))
    ok("full mode shows 65 questions / 130 min", "65 questions · 130 min" in pg.inner_text(".mk"))
    pg.click('[data-mode="short"]')
    ok("short mode shows 20 questions / 40 min", "20 questions · 40 min" in pg.inner_text(".mk"))
    pg.click('[data-act="start"]'); pg.wait_for_selector(".mkbar")
    st = state(pg)
    ok("20 questions drawn", len(st["ids"]) == 20)
    ok("timer running", ":" in pg.inner_text(".mkbar .timer"))
    ok("answers hidden during exam", pg.locator("#mockRoot .choice.correct").count() == 0 and pg.locator("#mockRoot .explain").count() == 0)
    # answer: first 12 correct, next 5 wrong, last 3 unanswered; flag 2
    expect_correct = 0
    for i, qid in enumerate(st["ids"][:17]):
        q = data["SAA-C03"][qid]; want = q["correctKeys"]
        keys = want if i < 12 else [k for k in [c["key"] for c in q["choices"]] if k not in want][:1]
        for k in keys: pg.click(f'#mockRoot .choice[data-key="{k}"]')
        if i < 12: expect_correct += 1
        if i in (3, 8): pg.click('[data-act="flag"]')
        if i == 6:
            pg.reload(); pg.wait_for_selector(".mkbar")
            ok("reload resumes on same question", pg.inner_text(".qnum").startswith("Question 7 of 20"))
            ok("answers survive reload", state(pg)["answers"].get(qid) == keys)
        pg.click('[data-act="next"]')
    ok("progress counter", "17/20 answered" in pg.inner_text(".mkbar"))
    ok("previous works", True)
    pg.click('[data-act="grid"]'); pg.wait_for_selector(".grid")
    ok("grid shows 17 answered", pg.locator(".cell.ans").count() == 17)
    ok("grid shows 2 flagged", pg.locator(".cell.flg").count() == 2)
    pg.click('[data-go="0"]'); pg.wait_for_selector(".qnum")
    ok("jump from grid", pg.inner_text(".qnum").startswith("Question 1 of 20"))
    pg.click('[data-act="grid"]')
    pg.click('[data-act="ask"]')
    ok("confirm warns about unanswered", "3 unanswered" in pg.inner_text(".confirm"))
    pg.click('[data-act="submit"]'); pg.wait_for_selector("#mockRoot .score")
    ok("score correct (12/20)", pg.inner_text("#mockRoot .score") == "60%" and "12 of 20 correct" in pg.inner_text(".mk"))
    ok("verdict needs work", "Needs work" in pg.inner_text(".verdict"))
    dom_total = sum(int(t.split("/")[1].split(" ")[0]) for t in pg.locator(".dom .top span:last-child").all_inner_texts() if "/" in t)
    ok("domain totals add up to 20", dom_total == 20, dom_total)
    ok("active state cleared", state(pg) is None)
    pg.click('[data-review="incorrect"]'); pg.wait_for_selector(".rv")
    ok("review incorrect lists 8", pg.locator(".rv").count() == 8)
    ok("review shows explanation + answer", pg.locator(".rv .ans-line").count() == 8)
    pg.click('[data-filter="flagged"]')
    ok("review flagged lists 2", pg.locator(".rv").count() == 2)
    pg.click('[data-filter="all"]')
    ok("review all lists 20", pg.locator(".rv").count() == 20)
    # diagram inside review for a drawn question that has one
    ids = set(json.load(open(ROOT + "/diagrams/index.json"))["ids"])
    with_diag = [q for q in st["ids"] if q in ids]
    if with_diag:
        pg.wait_for_selector(f"#mk-explain-{with_diag[0]} figure.qb-diagram", state="attached", timeout=8000)
        ok("diagram renders in review", True)
    bm = pg.locator(".rv [data-bm]").first; bm.click()
    ok("bookmark from review", "★" in bm.inner_text())
    sw = pg.evaluate("document.documentElement.scrollWidth")
    ok("no horizontal overflow on mobile", sw <= 390, sw)
    pg.screenshot(path="/tmp/mock_review.png")
    pg.click('[data-act="results"]'); pg.click('[data-act="new"]'); pg.wait_for_selector("#mkExam")
    ok("history shows attempt", "12/20 (60%)" in pg.inner_text(".mk"))
    pool_n = len(data["SAA-C03"])
    ok("seen count reduced by 20", f"{pool_n - 20} not yet seen" in pg.inner_text(".mk"), pg.inner_text(".meta"))
    pg.click('[data-act="exit"]'); pg.wait_for_selector(".qcard")
    ok("exit returns to bank", not pg.evaluate("document.querySelector('.wrap').hidden") and pg.evaluate("location.hash") == "#exam=SAA-C03")
    ok("bookmark count updated", pg.inner_text(".bookmarks-chip .cnt") == "1", pg.inner_text("#chipRow")[:60])

    # multi-answer question + timer auto-submit via injected state
    multi = [q for q in data["AIP-C01"].values() if len(q["correctKeys"]) > 1][0]
    single = [q for q in data["AIP-C01"].values() if len(q["correctKeys"]) == 1][0]
    inj = {"v": 1, "exam": "AIP-C01", "mode": "short", "ids": [multi["id"], single["id"]],
           "order": {multi["id"]: [c["key"] for c in multi["choices"]][::-1], single["id"]: [c["key"] for c in single["choices"]]},
           "answers": {}, "flags": [], "cur": 0, "startedAt": int(time.time() * 1000), "duration": 3600, "timed": True,
           "deadline": int(time.time() * 1000) + 3600_000, "submitted": False}
    pg.evaluate("s => localStorage.setItem('aws_qbank_mock_active_v1', JSON.stringify(s))", inj)
    pg.goto(BASE + "#mock=AIP-C01"); pg.reload(); pg.wait_for_selector(".mkbar")
    ok("resumes injected exam", "AIP-C01" in pg.inner_text(".mkbar"))
    ok("multi note shown", f"Select {len(multi['correctKeys'])}" in pg.inner_text(".mk"))
    for k in multi["correctKeys"]: pg.click(f'#mockRoot .choice[data-key="{k}"]')
    ok("multi keeps both selections", pg.locator("#mockRoot .choice.picked").count() == len(multi["correctKeys"]))
    # expire the timer
    pg.evaluate("() => { const s = JSON.parse(localStorage.getItem('aws_qbank_mock_active_v1')); s.deadline = Date.now() + 1500; localStorage.setItem('aws_qbank_mock_active_v1', JSON.stringify(s)); }")
    pg.reload(); pg.wait_for_selector("#mockRoot .score", timeout=8000)
    ok("timer auto-submits", "submitted automatically" in pg.inner_text(".mk"))
    ok("multi answer scored correct (1/2)", "1 of 2 correct" in pg.inner_text(".mk"))
    ok("no page errors", not errs, errs)
    ctx.close()

    # dark mode + desktop screenshot of exam screen
    ctx = b.new_context(color_scheme="dark", viewport={"width": 900, "height": 900})
    pg = ctx.new_page(); pg.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    pg.goto(BASE + "#mock=SCS-C03"); pg.wait_for_selector("#mkExam")
    ok("deep link opens setup for SCS-C03", pg.eval_on_selector("#mkExam", "e=>e.value") == "SCS-C03")
    pg.click('[data-act="start"]'); pg.wait_for_selector(".mkbar")
    ok("full SCS exam has 65 questions", len(state(pg)["ids"]) == 65)
    pg.screenshot(path="/tmp/mock_exam_dark.png")
    pg.goto(BASE + "#exam=DVA-C02"); pg.reload(); pg.wait_for_selector(".qcard")
    pg.click("#mockBtn"); pg.wait_for_selector(".mkbar")
    ok("mock button resumes the running exam", "SCS-C03" in pg.inner_text(".mkbar"))
    pg.go_back(); pg.wait_for_timeout(600)
    ok("browser back leaves mock mode", not pg.evaluate("document.querySelector('.wrap').hidden") and pg.evaluate("document.getElementById('mockRoot').hidden"))
    ctx.close(); b.close()
srv.shutdown()
f = [n for n, c in res if not c]
print(f"{len(res) - len(f)}/{len(res)} passed"); sys.exit(1 if f else 0)
