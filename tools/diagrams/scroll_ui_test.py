import functools, http.server, threading, sys
from playwright.sync_api import sync_playwright
import pathlib
ROOT=str(pathlib.Path(__file__).resolve().parents[2])
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=http.server.ThreadingHTTPServer(("127.0.0.1",0),functools.partial(Q,directory=ROOT))
threading.Thread(target=srv.serve_forever,daemon=True).start()
BASE=f"http://127.0.0.1:{srv.server_address[1]}/"
res=[]
def ok(n,c): res.append((n,bool(c))); print(("PASS " if c else "FAIL ")+n)
with sync_playwright() as p:
    b=p.chromium.launch()
    for scheme in ("light","dark"):
        ctx=b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,color_scheme=scheme)
        pg=ctx.new_page(); errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
        pg.route("**/fonts.googleapis.com/**",lambda r:r.abort())
        pg.goto(BASE+"#exam=SAP-C02"); pg.wait_for_selector(".qcard")
        vis=lambda sel: pg.evaluate(f"document.querySelector('{sel}').classList.contains('show')")
        ok(f"[{scheme}] bar hidden at top", not vis("#examBar"))
        ok(f"[{scheme}] top button hidden at top", not vis("#toTop"))
        pg.mouse.wheel(0,3000); pg.wait_for_timeout(500)
        ok(f"[{scheme}] bar shown after scroll", vis("#examBar"))
        ok(f"[{scheme}] bar shows SAP-C02", pg.inner_text("#examBarCode")=="SAP-C02" and "Professional" in pg.inner_text("#examBarName"))
        chip_top=pg.evaluate("document.getElementById('chipRow').getBoundingClientRect().bottom")
        ok(f"[{scheme}] chip row scrolled away (not sticky)", chip_top<0)
        ok(f"[{scheme}] top button shown", vis("#toTop"))
        bh=pg.evaluate("document.getElementById('examBar').getBoundingClientRect().height")
        ok(f"[{scheme}] bar is compact ({bh:.0f}px)", bh<=48)
        pg.screenshot(path=f"/tmp/scroll_{scheme}.png")
        # answer a question while scrolled -> score appears in bar
        card=pg.locator(".qcard").nth(5); card.scroll_into_view_if_needed(); card.locator(".choice").first.click(); pg.wait_for_timeout(300)
        ok(f"[{scheme}] bar shows score", "/" in pg.inner_text("#examBarScore"))
        pg.click("#examBarChange"); pg.wait_for_timeout(900)
        ct=pg.evaluate("document.getElementById('chipRow').getBoundingClientRect().top")
        ok(f"[{scheme}] Change scrolls to chips (top={ct:.0f})", -5<=ct<=60)
        pg.mouse.wheel(0,4000); pg.wait_for_timeout(400)
        pg.click("#toTop"); pg.wait_for_timeout(1200)
        ok(f"[{scheme}] top button returns to top", pg.evaluate("window.scrollY")<5)
        pg.wait_for_timeout(300)
        ok(f"[{scheme}] bar hides again at top", not vis("#examBar"))
        # bookmarks view label
        pg.goto(BASE+"#bookmarks"); pg.reload(); pg.wait_for_timeout(800)
        pg.goto(BASE+"#exam=SAA-C03"); pg.wait_for_selector(".qcard")
        pg.locator(".qcard .bookmark-btn").first.click()
        pg.locator('.chip[data-code="__bookmarks__"], .bookmarks-chip').first.click(); pg.wait_for_timeout(300)
        ok(f"[{scheme}] bookmarks label", "Bookmarks" in pg.inner_text("#examBarCode"))
        pg.locator(".qcard .bookmark-btn").first.click()
        ok(f"[{scheme}] no page errors", not errs); 
        if errs: print(errs)
        ctx.close()
    b.close()
srv.shutdown()
f=[n for n,c in res if not c]; print(f"{len(res)-len(f)}/{len(res)} passed"); sys.exit(1 if f else 0)
