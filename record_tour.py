"""Record a ~85s captioned dextran-story tour of the Coacervation site.

Story: %T overlay of the 0.4% dextran series (APG chassis, by Batch ID) ->
scroll to fingerprint + AUC -> Performance Library DRF for the SAME dextrans
WITH silicone (S150) -> short SCG phase-diagram example.
Captions are pinned to the BOTTOM. Saves webm; convert to mp4 separately.
"""
import json
import os
import shutil
from playwright.sync_api import sync_playwright

URL = "http://localhost:5001/"
OUTDIR = "Reports"
TMP = os.path.join(OUTDIR, "_video_tmp")
os.makedirs(TMP, exist_ok=True)
SIL = "B-20260803-00983,B-20260803-00985,B-20260803-01106"


def cap(page, text):
    page.evaluate(
        """(t) => {
            let el = document.getElementById('__cap');
            if (!el) {
                el = document.createElement('div'); el.id = '__cap';
                document.body.appendChild(el);
                Object.assign(el.style, {position:'fixed', bottom:'26px', left:'50%',
                    transform:'translateX(-50%)', zIndex:999999,
                    background:'rgba(0,38,106,0.96)', color:'#fff',
                    padding:'12px 22px', borderRadius:'10px',
                    font:'600 18px "Segoe UI", sans-serif',
                    boxShadow:'0 6px 18px rgba(0,0,0,.4)', maxWidth:'84%',
                    textAlign:'center', letterSpacing:'.2px'});
            }
            el.textContent = t;
        }""", text)


def click_tab(page, group):
    page.click(f'.tab[data-group="{group}"]')
    page.wait_for_timeout(900)


def top(page):
    page.evaluate("window.scrollTo({top:0})")
    page.wait_for_timeout(400)


def scroll_to(page, sel):
    page.evaluate(f"const e=document.querySelector({json.dumps(sel)});"
                  "if(e) e.scrollIntoView({behavior:'smooth', block:'center'});")
    page.wait_for_timeout(1500)


def scroll_by(page, dy):
    page.evaluate(f"window.scrollBy({{top:{dy}, behavior:'smooth'}});")
    page.wait_for_timeout(1400)


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport={"width": 1440, "height": 900},
        record_video_dir=TMP,
        record_video_size={"width": 1440, "height": 900},
    )
    page = ctx.new_page()

    # 1) Home
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(900)
    cap(page, "Coacervation Analysis \u2014 a worked dextran example, end to end")
    page.wait_for_timeout(3200)

    # 2) Analyze %T - overlay the 0.4% dextran series by Batch ID
    click_tab(page, "analyze")
    top(page)
    cap(page, "Analyze %T: pull samples by Batch ID and overlay them on one graph")
    page.wait_for_timeout(1400)

    def add_by_batch(bid):
        page.fill("#sampleSearch", "")
        page.type("#sampleSearch", bid, delay=20)
        page.wait_for_selector(".sampleRow", timeout=9000)
        page.wait_for_timeout(800)
        page.locator(".sampleRow").first.click()
        page.wait_for_timeout(1000)

    add_by_batch("B-20260722-01448")   # APG 0.4% CD2
    add_by_batch("B-20260722-01449")   # APG 0.4% Dex-B
    add_by_batch("B-20260722-01466")   # APG 0.4% Dex-K
    cap(page, "Three 0.4% dextrans in the APG chassis \u2014 CD2 vs Dex-B vs Dex-K")
    page.wait_for_timeout(1600)
    page.click("#analyzeBtn")
    cap(page, "Plotting %T + Absorbance and the coacervation fingerprints\u2026")
    try:
        page.wait_for_selector("#tab-analyze img", timeout=25000)
    except Exception:
        page.wait_for_timeout(4000)
    page.wait_for_timeout(1400)
    scroll_to(page, "#tab-analyze img")
    cap(page, "Overlaid dilution curves \u2014 %T and Absorbance on one graph")
    page.wait_for_timeout(3600)
    scroll_by(page, 430)
    cap(page, "Scroll down: the AUC comparison \u2014 coacervation strength, ranked")
    page.wait_for_timeout(3800)
    scroll_by(page, 430)
    cap(page, "\u2026and each sample's coacervation fingerprint (onset, peak, breadth)")
    page.wait_for_timeout(4200)

    # 3) Performance Library - the SAME dextrans WITH silicone (S150), DRF
    page.evaluate(f"location.hash = '#view=ptl_dash&b={SIL}'")
    page.reload(wait_until="domcontentloaded")
    cap(page, "Performance Library: the SAME dextrans, now WITH silicone (S150)")
    try:
        page.wait_for_function(
            "document.querySelector('#ptlDashOut') && "
            "!document.querySelector('#ptlDashOut .muted')", timeout=20000)
    except Exception:
        page.wait_for_timeout(4000)
    page.wait_for_timeout(1200)
    scroll_to(page, "#ptlDashOut")
    cap(page, "SACS combing friction, S150: lower = better. 3196 lowest, Dex-K highest")
    page.wait_for_timeout(4000)
    scroll_by(page, 430)
    cap(page, "Silicone flips the story \u2014 the %T ranking alone doesn't predict conditioning")
    page.wait_for_timeout(4000)

    # 4) Phase diagram - quick SCG example
    click_tab(page, "analyze")
    try:
        page.get_by_role("button", name="Phase diagram").first.click()
        page.wait_for_timeout(1000)
        top(page)
        page.fill("#phExpSearch", "")
        page.type("#phExpSearch", "N3196 + SCG", delay=25)
        page.wait_for_timeout(1200)
        page.locator("#phExpSuggest").get_by_text("SCG", exact=False).first.click()
        page.wait_for_timeout(600)
        cap(page, "Phase diagrams: map coacervation across surfactants \u2014 the SCG series")
        page.click("#phPlotBtn")
        try:
            page.wait_for_selector("#phPlot img", timeout=20000)
        except Exception:
            page.wait_for_timeout(5000)
        page.wait_for_timeout(1200)
        scroll_to(page, "#phPlot")
        page.wait_for_timeout(4500)
    except Exception:
        pass

    # 5) Close
    cap(page, "One platform: %T screening \u2192 silicone performance \u2192 mechanism")
    page.wait_for_timeout(3000)

    video_path = page.video.path()
    ctx.close()
    browser.close()

final_webm = os.path.join(OUTDIR, "coacervation_tour.webm")
if os.path.exists(final_webm):
    os.remove(final_webm)
shutil.move(video_path, final_webm)
try:
    shutil.rmtree(TMP)
except OSError:
    pass
print("WEBM:", final_webm, os.path.getsize(final_webm), "bytes")
