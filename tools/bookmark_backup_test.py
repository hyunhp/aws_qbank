import subprocess, time, json, sys
from playwright.sync_api import sync_playwright
srv = subprocess.Popen(["python3","-m","http.server","8765"],cwd="/home/claude/aws_qbank",stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(1.2)
ok=0; fail=0
def check(name,cond,info=""):
    global ok,fail
    if cond: ok+=1
    else: fail+=1; print("FAIL",name,info)
try:
  with sync_playwright() as p:
    b=p.chromium.launch()
    ctx=b.new_context(accept_downloads=True, permissions=["clipboard-read","clipboard-write"])
    pg=ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8765/#exam=SAA-C03"); pg.wait_for_selector(".qcard")
    check("tools hidden in exam view", not pg.is_visible("#bmTools"))
    btns=pg.query_selector_all(".bookmark-btn")[:3]
    ids=[x.get_attribute("data-qid") for x in btns]
    for x in btns: x.click()
    pg.click(".bookmarks-chip"); pg.wait_for_timeout(300)
    check("tools visible in bookmark view", pg.is_visible("#bmTools"))
    check("3 cards", len(pg.query_selector_all(".qcard"))==3)
    pg.click("#bmCopyLink"); pg.wait_for_timeout(300)
    link=pg.evaluate("navigator.clipboard.readText()")
    check("link format", "#bm=" in link, link)
    with pg.expect_download() as dl: pg.click("#bmExport")
    path=dl.value.path(); data=json.load(open(path))
    check("export contents", sorted(data["bookmarks"])==sorted(ids), data)
    # fresh context: restore by link
    ctx2=b.new_context(); pg2=ctx2.new_page(); pg2.on("pageerror", lambda e: errs.append(str(e)))
    pg2.goto(link.replace("https://","http://")); pg2.wait_for_timeout(1500)
    check("restored via link", sorted(pg2.evaluate("JSON.parse(localStorage.getItem('aws_qbank_bookmarks_v1'))"))==sorted(ids))
    check("hash normalized", pg2.evaluate("location.hash")=="#bookmarks")
    check("restored cards shown", len(pg2.query_selector_all(".qcard"))==3)
    check("toast shown", "Restored 3" in (pg2.inner_text("body")))
    # fresh context: import file
    ctx3=b.new_context(); pg3=ctx3.new_page(); pg3.on("pageerror", lambda e: errs.append(str(e)))
    pg3.goto("http://localhost:8765/#bookmarks"); pg3.wait_for_timeout(1200)
    check("empty state", "haven't bookmarked" in pg3.inner_text("#listArea"))
    check("tools visible when empty", pg3.is_visible("#bmTools"))
    pg3.set_input_files("#bmImportFile", path); pg3.wait_for_timeout(500)
    check("imported cards", len(pg3.query_selector_all(".qcard"))==3)
    check("chip count", "3" in pg3.inner_text(".bookmarks-chip"))
    # re-import is idempotent
    pg3.set_input_files("#bmImportFile", path); pg3.wait_for_timeout(500)
    check("idempotent import", len(pg3.query_selector_all(".qcard"))==3)
    # bad file
    open("/tmp/bad.json","w").write("not json")
    pg3.set_input_files("#bmImportFile", "/tmp/bad.json"); pg3.wait_for_timeout(300)
    check("bad file message", "could not be read" in pg3.inner_text("body"))
    # manifest reachable
    r=pg3.request.get("http://localhost:8765/manifest.webmanifest"); check("manifest", r.ok and "AWS QBank" in r.text())
    # encode/decode round trip for many ids
    rt=pg3.evaluate("(()=>{const ids=['Q000001','Q004044','Q000150','Q002000'];return decodeBookmarks(encodeBookmarks(new Set(ids))).sort().join()})()")
    check("roundtrip", rt=="Q000001,Q000150,Q002000,Q004044", rt)
    check("no page errors", not errs, errs)
    b.close()
finally:
    srv.terminate()
print(f"{ok}/{ok+fail} passed"); sys.exit(1 if fail else 0)
