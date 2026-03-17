"""
BrowserSession — owns the playwright + context lifecycle for one site.
All site modules use this to open/close their browser; main.py keeps
sessions alive across search → add-to-cart so windows never reopen.
"""
from pathlib import Path
from playwright.async_api import Page

PROFILE_DIR = Path.home() / ".buylinkit" / "profiles"

_NO_LOCATION_SIGNALS = {
    "Blinkit":   ["set your location", "detect my location", "enter your location"],
    "Zepto":     ["select location", "enter your pincode", "enter pincode"],
    "Instamart": ["detect location", "enter your location", "set location"],
}


class BrowserSession:
    """
    Manages one persistent Chromium profile for one site.
    Call await session.start() to open the browser and get the page.
    Call await session.close() when done.
    """

    def __init__(self, site_key: str, x: int, y: int,
                 width: int = 720, height: int = 760):
        self.site_key  = site_key
        self._profile  = str(PROFILE_DIR / site_key)
        self._x        = x
        self._y        = y
        self._width    = width
        self._height   = height
        self._pw       = None
        self._ctx      = None
        self._page     = None

    async def start(self) -> Page:
        from playwright.async_api import async_playwright
        Path(self._profile).mkdir(parents=True, exist_ok=True)
        self._pw  = await async_playwright().start()
        self._ctx = await self._pw.chromium.launch_persistent_context(
            self._profile,
            headless=False,
            args=[
                f"--window-size={self._width},{self._height}",
                f"--window-position={self._x},{self._y}",
            ],
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
        return self._page

    @property
    def page(self) -> Page:
        return self._page

    async def close(self):
        try:
            if self._ctx:
                await self._ctx.close()
        except Exception:
            pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Location helper
# ---------------------------------------------------------------------------

def _location_missing(page_text: str, site: str) -> bool:
    text_lower = page_text.lower()
    signals    = _NO_LOCATION_SIGNALS.get(site, [])
    preview    = text_lower[:500]
    has_signal = any(s in preview for s in signals)
    has_prices = "₹" in text_lower[:2000]
    return has_signal and not has_prices


async def ensure_location(page: Page, page_text: str, site: str) -> str:
    if not _location_missing(page_text, site):
        return page_text
    print(f"\n📍 [{site}] Location not set — set your delivery address in the "
          f"browser window, then press Enter here.")
    try:
        input("   Press Enter once location is set… ")
    except EOFError:
        pass
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)
        return await page.inner_text("body")
    except Exception:
        return page_text


# ---------------------------------------------------------------------------
# ADD-button clicker  (index-based primary, name-based fallback)
# ---------------------------------------------------------------------------

async def click_add_button(page: Page, product_name: str,
                           product_index: int = 0) -> bool:
    """
    Click the ADD button for the product at position `product_index`
    within the product grid.

    Primary: find the tightest container that has ≥3 ADD buttons (the grid),
    then click the Nth ADD button inside it — matches the order the LLM saw.

    Fallback: walk up at most 3 ancestor levels from each ADD button,
    bail if the container text exceeds 350 chars (shared parent).
    """
    clicked = await page.evaluate("""
        (function(targetIdx) {
            const isAdd = b => b.innerText.trim().toUpperCase() === 'ADD';
            const allAdds = [...document.querySelectorAll('button,[role="button"]')]
                .filter(isAdd);
            if (!allAdds.length) return false;

            // Walk up from every ADD button to find the tightest container
            // that holds >= 3 ADD buttons (= the product grid).
            let grid = null, gridCount = 0;
            for (const btn of allAdds) {
                let el = btn.parentElement;
                while (el && el !== document.body) {
                    const n = [...el.querySelectorAll('button,[role="button"]')]
                        .filter(isAdd).length;
                    if (n >= 3 && n > gridCount && el.innerText.length < 30000) {
                        gridCount = n; grid = el;
                    }
                    el = el.parentElement;
                }
            }

            const src  = grid || document;
            const adds = [...src.querySelectorAll('button,[role="button"]')]
                .filter(isAdd);
            if (targetIdx < adds.length) { adds[targetIdx].click(); return true; }
            return false;
        })
    """, product_index)

    if clicked:
        return True

    # Name-based fallback
    name_lower = product_name.lower()[:50]
    return await page.evaluate("""
        (function(lower) {
            const isAdd = b => b.innerText.trim().toUpperCase() === 'ADD';
            const buttons = [...document.querySelectorAll('button,[role="button"]')]
                .filter(isAdd);
            let best = null, bestScore = 0;
            for (const btn of buttons) {
                let el = btn;
                for (let i = 0; i < 3; i++) {
                    if (!el.parentElement) break;
                    el = el.parentElement;
                    const txt = el.innerText.toLowerCase();
                    if (txt.length > 350) break;
                    if (txt.includes(lower)) {
                        const score = lower.length / txt.length;
                        if (score > bestScore) { bestScore = score; best = btn; }
                        break;
                    }
                }
            }
            if (best) { best.click(); return true; }
            return false;
        })
    """, name_lower)
