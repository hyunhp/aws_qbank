"""Regression tests for opening mock exams by link, including stale saved exam state."""
import subprocess, time, json, sys
from playwright.sync_api import sync_playwright
PORT = 8768
srv = subprocess.Popen(["python3", "-m", "http.server", str(PORT)], cwd="/home/claude/aws_qbank",
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.2)
BASE = f"http://localhost:{PORT}/"
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    if cond: ok += 1
    else: fail += 1; print("FAIL", name, info)
def active(ids, **kw):
    d = {"v": 1, "exam": "SOA-C03", "mode": "short", "ids": ids, "order": {}, "answers": {}, "flags": [], "cur": 0,
         "startedAt": 0, "duration": 1000, "timed": False, "deadline": None, "submitted": False}
    d.update(kw); return json.dumps(d)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        soa = json.load(open("/home/claude/aws_qbank/data/SOA-C03.json"))
        real = [q["id"] for q in soa[:5]]
        cases = [
            ("fresh", None, "setup"),
            ("all ids stale", active(["Q999998", "Q999999"]), "setup"),
            ("some ids stale", active(real[:3] + ["Q999999"], cur=3, answers={"Q999999": ["A"], real[0]: ["A"]}), "exam"),
            ("bad order", active(real[:2], order={real[0]: ["Z"]}), "exam"),
            ("unknown exam", active(real[:2], exam="XYZ-C01"), "setup"),
            ("corrupt json", "{bad", "setup"),
        ]
        for label, saved, expect in cases:
            ctx = b.new_context(); pg = ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
            pg.goto(BASE + "#exam=SAA-C03"); pg.wait_for_selector(".qcard")
            if saved is not None: pg.evaluate(f"localStorage.setItem('aws_qbank_mock_active_v1', {json.dumps(saved)})")
            pg.goto(BASE + "#mock=SOA-C03"); pg.reload(); pg.wait_for_timeout(2000)
            txt = pg.inner_text("#mockRoot")
            check(f"{label}: not blank", len(txt) > 50, txt[:80])
            if expect == "setup": check(f"{label}: setup shown", "Start exam" in txt, txt[:80])
            else: check(f"{label}: exam resumed", "answered" in txt and "SOA-C03" in txt, txt[:80])
            if label == "some ids stale":
                st = json.loads(pg.evaluate("localStorage.getItem('aws_qbank_mock_active_v1')"))
                check("stale id pruned", "Q999999" not in st["ids"] and len(st["ids"]) == 3, st["ids"])
                check("cur clamped", st["cur"] == 2, st["cur"])
                check("stale answer pruned", "Q999999" not in st["answers"], st["answers"])
            check(f"{label}: no page errors", not errs, errs)
            ctx.close()
        # hash navigation from an open page opens the mock exam
        ctx = b.new_context(); pg = ctx.new_page()
        pg.goto(BASE + "#exam=SAA-C03"); pg.wait_for_selector(".qcard")
        pg.evaluate("location.hash = 'mock=SOA-C03'"); pg.wait_for_timeout(1500)
        check("hash nav opens mock", not pg.evaluate("document.getElementById('mockRoot').hidden") and "SOA-C03" in pg.inner_text("#mockRoot"))
        pg.go_back(); pg.wait_for_timeout(800)
        check("back closes mock", pg.evaluate("document.getElementById('mockRoot').hidden"))
        ctx.close(); b.close()
finally:
    srv.terminate()
print(f"{ok}/{ok+fail} passed"); sys.exit(1 if fail else 0)
