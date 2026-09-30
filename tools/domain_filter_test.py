"""Section (domain/task) filter, per-domain accuracy and hash links (Playwright, local server).

- Domain chips show the counts of each exam domain (shared questions use exam-domains.json), the task row
  lists the tasks of the chosen domain.
- Filter state lives in the URL hash (#exam=X&d=D4&t=T4.1); a stale domain in a link falls back to all.
- Counted answers are recorded per domain in localStorage; a domain below 70% after 5 answers is flagged.
- The stats never leave the browser: the bookmark backup contains bookmarks only.
    python3 tools/domain_filter_test.py
"""
import collections, functools, http.server, json, pathlib, re, sys, threading
from playwright.sync_api import sync_playwright

ROOT = str(pathlib.Path(__file__).resolve().parents[1])
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/"
def jload(*p): return json.load(open(pathlib.Path(ROOT, *p), encoding="utf-8"))
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    if cond: ok += 1
    else: fail += 1; print("FAIL", name, info)

EXAM = "AIF-C01"
qs = jload("data", f"{EXAM}.json")
dmap = jload("data", "exam-domains.json")
def dom(q): return q["domainCode"] if q["examCodes"][0] == EXAM else dmap.get(q["id"], {}).get(EXAM, q["domainCode"])
want = collections.Counter(dom(q) for q in qs)
tasks_d4 = collections.Counter(q["taskId"] for q in qs if dom(q) == "D4" and q["examCodes"][0] == EXAM)
by_id = {q["id"]: q for q in qs}
shared_other = [q for q in qs if q["examCodes"][0] != EXAM and q["id"] in dmap and EXAM in dmap[q["id"]]]

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    pg.goto(BASE + f"#exam={EXAM}"); pg.wait_for_selector(".qcard")
    pg.wait_for_selector("#domainRow .fchip[data-d='D4']")
    chips = pg.eval_on_selector_all("#domainRow .fchip[data-d]", "els => els.map(e => [e.dataset.d, (e.querySelector('.cnt') || {}).textContent])")
    got = {d: int(c) for d, c in chips if d}
    check("domain chips match data counts", got == dict(want), (got, dict(want)))
    check("All chip shows total", chips[0][1] == str(len(qs)), chips[0])
    check("cards = all questions", pg.locator(".qcard").count() == len(qs))
    check("task row hidden without a domain", pg.locator("#taskRow").is_hidden())
    if shared_other:
        check("shared question counted in this exam's domain", want[dom(shared_other[0])] > 0)

    pg.click("#domainRow .fchip[data-d='D4']"); pg.wait_for_selector(".qcard")
    check("D4 filter card count", pg.locator(".qcard").count() == want["D4"], pg.locator(".qcard").count())
    check("hash has domain", "d=D4" in pg.evaluate("location.hash"), pg.evaluate("location.hash"))
    tchips = pg.eval_on_selector_all("#taskRow .fchip[data-t]", "els => els.map(e => [e.dataset.t, (e.querySelector('.cnt') || {}).textContent])")
    check("task chips of D4", {t: int(c) for t, c in tchips if t} == dict(tasks_d4), (tchips, dict(tasks_d4)))
    shown = pg.eval_on_selector_all(".qcard", "els => els.map(e => e.dataset.qid)")
    check("only D4 questions listed", all(dom(by_id[i]) == "D4" for i in shown))

    pg.click("#taskRow .fchip[data-t='T4.1']"); pg.wait_for_timeout(300)
    check("task filter card count", pg.locator(".qcard").count() == tasks_d4["T4.1"], pg.locator(".qcard").count())
    check("hash has task", "t=T4.1" in pg.evaluate("location.hash"))

    # direct link and stale links
    pg.goto(BASE + f"?x=1#exam={EXAM}&d=D4&t=T4.2"); pg.wait_for_selector(".qcard")
    check("link restores task filter", pg.locator(".qcard").count() == tasks_d4["T4.2"], pg.locator(".qcard").count())
    check("active chips from link", pg.locator("#domainRow .fchip.active[data-d='D4']").count() == 1 and pg.locator("#taskRow .fchip.active[data-t='T4.2']").count() == 1)
    pg.goto(BASE + f"?x=2#exam={EXAM}&d=D9"); pg.wait_for_selector(".qcard")
    check("stale domain falls back to all", pg.locator(".qcard").count() == len(qs))
    pg.goto(BASE + "?x=3#exam=SAA-C03"); pg.wait_for_selector(".qcard")
    check("filter row for another exam", pg.locator("#domainRow .fchip[data-d]").count() >= 4)
    pg.click(".chip[data-code='AIF-C01']"); pg.wait_for_selector(".qcard")
    check("switching exam clears filter", "d=" not in pg.evaluate("location.hash"))

    # accuracy: five wrong answers in D4 flag the domain
    pg.goto(BASE + f"?x=4#exam={EXAM}&d=D4"); pg.wait_for_selector(".qcard")
    pg.click("#sequentialBtn"); pg.wait_for_selector(".qcard")
    single = [q for q in qs if dom(q) == "D4" and len(q["correctKeys"]) == 1][:5]
    for q in single:
        wrong = [c["key"] for c in q["choices"] if c["key"] not in q["correctKeys"]][0]
        pg.evaluate(f"document.getElementById('card-{q['id']}').scrollIntoView({{block:'center'}})")
        pg.click(f"#card-{q['id']} .choice[data-key='{wrong}']")
        pg.wait_for_selector(f"#explain-{q['id']}.show")
    stats = pg.evaluate("JSON.parse(localStorage.getItem('aws_qbank_domain_stats_v1'))")
    check("stats recorded for the domain", stats.get(EXAM, {}).get("D4") == [0, 5], stats)
    pg.click("#domainRow .fchip[data-d='']"); pg.wait_for_selector(".qcard")
    chip = pg.locator("#domainRow .fchip[data-d='D4']")
    check("weak domain flagged", "weak" in (chip.get_attribute("class") or "") and "0%" in chip.inner_text(), chip.inner_text())
    check("focus link points at weakest", pg.locator("#domainRow [data-focus='D4']").count() == 1)
    pg.click("#domainRow [data-focus='D4']"); pg.wait_for_selector(".qcard")
    check("focus link filters", pg.locator(".qcard").count() == want["D4"])

    # stats persist across reload; not part of the bookmark backup
    pg.reload(); pg.wait_for_selector("#domainRow .fchip.weak")
    check("stats survive reload", pg.locator("#domainRow .fchip.weak[data-d='D4']").count() == 1)
    pg.evaluate(f"localStorage.setItem('aws_qbank_bookmarks_v1', JSON.stringify(['{qs[0]['id']}']))")
    pg.goto(BASE + "?x=5#bookmarks"); pg.wait_for_selector(".qcard")
    check("no filter row in bookmarks", pg.locator("#domainRow").is_hidden() and pg.locator("#taskRow").is_hidden())
    with pg.expect_download() as dl:
        pg.click("#bmExport")
    exported = json.load(open(dl.value.path(), encoding="utf-8"))
    check("backup file has bookmarks only", set(exported) == {"app", "version", "exported", "bookmarks"}, list(exported))
    pg.goto(BASE + f"?x=6#exam={EXAM}"); pg.wait_for_selector("#domainRow [data-resetstats]")
    pg.once("dialog", lambda d: d.accept())
    pg.click("#domainRow [data-resetstats]"); pg.wait_for_timeout(300)
    check("reset stats clears the flag", pg.locator("#domainRow .fchip.weak").count() == 0)
    # mock exam: "this section only" from the active filter, and from a link
    pg.goto(BASE + f"?x=7#exam={EXAM}&d=D4"); pg.wait_for_selector(".qcard")
    pg.click("#mockBtn"); pg.wait_for_selector("#mkDomain")
    check("mock setup preselects the section", pg.eval_on_selector("#mkDomain", "e => e.value") == "D4")
    pg.click("[data-mode='short']"); pg.wait_for_selector("[data-mode='short'].on")
    pg.click("[data-act='start']"); pg.wait_for_selector(".mkbar")
    active = pg.evaluate("JSON.parse(localStorage.getItem('aws_qbank_mock_active_v1'))")
    check("focused mock size", len(active["ids"]) == min(20, want["D4"]), len(active["ids"]))
    check("focused mock only D4", all(dom(by_id[i]) == "D4" for i in active["ids"]))
    check("focused mock remembers the section", active.get("domain") == "D4", active.get("domain"))
    pg.evaluate("localStorage.removeItem('aws_qbank_mock_active_v1')")
    pg.goto(BASE + f"?x=8#mock={EXAM}&d=D5"); pg.wait_for_selector("#mkDomain")
    check("mock link preselects the section", pg.eval_on_selector("#mkDomain", "e => e.value") == "D5")
    pg.select_option("#mkDomain", ""); pg.wait_for_timeout(200)
    check("all sections option restores weights", pg.eval_on_selector("#mkDomain", "e => e.value") == "")
    check("no page errors", not errs, errs)
    b.close()
srv.shutdown()
print(f"{ok}/{ok+fail} passed"); sys.exit(1 if fail else 0)
