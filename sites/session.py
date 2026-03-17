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

_LOGIN_SIGNALS = {
    "Blinkit":   ["login to blinkit", "sign in", "enter your phone"],
    "Zepto":     ["login", "sign in", "enter your mobile", "enter mobile number"],
    "Instamart": ["login to swiggy", "sign in to swiggy", "enter your mobile"],
}


class BrowserSession:
    def __init__(self, site_key: str, x: int, y: int,
                 width: int = 600, height: int = 720):
        self.site_key  = site_key
        self._profile  = str(PROFILE_DIR / site_key)
        self._x        = x
        self._y        = y
        self._width    = width
        self._height   = height
        self._pw       = None
        self._ctx      = None
        self._page     = None

    _USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    async def start(self) -> Page:
        from playwright.async_api import async_playwright
        Path(self._profile).mkdir(parents=True, exist_ok=True)
        self._pw  = await async_playwright().start()
        self._ctx = await self._pw.chromium.launch_persistent_context(
            self._profile,
            headless=False,
            user_agent=self._USER_AGENT,
            args=[
                f"--window-size={self._width},{self._height}",
                f"--window-position={self._x},{self._y}",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
        await self._ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return self._page

    @property
    def page(self) -> Page:
        return self._page

    async def close(self):
        for attr in ("_ctx", "_pw"):
            obj = getattr(self, attr)
            if obj:
                try:
                    await obj.close() if attr == "_ctx" else await obj.stop()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Login / location detection
# ---------------------------------------------------------------------------

def needs_login(page_text: str, site: str, url: str = "") -> bool:
    """True if the page is a login wall — URL check is most reliable."""
    if any(x in url.lower() for x in ["login", "signin", "sign-in", "/auth"]):
        return True
    text_lower = page_text.lower()[:800]
    signals    = _LOGIN_SIGNALS.get(site, [])
    has_login  = any(s in text_lower for s in signals)
    has_prices = "₹" in page_text[:3000]
    return has_login and not has_prices


def needs_location(page_text: str, site: str) -> bool:
    """True if no delivery location is set."""
    text_lower = page_text.lower()
    signals    = _NO_LOCATION_SIGNALS.get(site, [])
    has_signal = any(s in text_lower[:500] for s in signals)
    has_prices = "₹" in text_lower[:2000]
    return has_signal and not has_prices


# ---------------------------------------------------------------------------
# Search helper — direct selectors + explicit Enter (no LLM needed)
# ---------------------------------------------------------------------------

_SEARCH_SELECTORS = [
    'input[type="search"]',
    '[role="searchbox"]',
    'input[placeholder*="search" i]',
    'input[placeholder*="looking" i]',
    'input[placeholder*="find" i]',
    'input[placeholder*="type here" i]',
    'input[placeholder*="item" i]',
    'input[placeholder*="product" i]',
]


async def do_search(page: Page, query: str, site: str) -> bool:
    """
    Find the search box using common selectors, fill the query, press Enter.
    Always presses Enter explicitly — some sites won't search otherwise.
    Falls back to LLM act() if no selector matches.
    """
    for sel in _SEARCH_SELECTORS:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=2000):
                await loc.click()
                await page.wait_for_timeout(300)
                await loc.fill(query)
                await page.wait_for_timeout(300)
                await page.keyboard.press("Enter")
                return True
        except Exception:
            continue

    # LLM fallback — still always press Enter after
    try:
        from llm import act
        await act(
            page,
            goal=f"Find the search box, click it, type '{query}', then press Enter.",
            site=site,
            max_steps=5,
        )
    except Exception:
        pass

    await page.keyboard.press("Enter")
    return True


# ---------------------------------------------------------------------------
# ADD-button clicker
# ---------------------------------------------------------------------------

async def click_add_button(page: Page, product_name: str,
                           product_index: int = 0) -> bool:
    """
    Primary: click the Nth ADD button in the product grid (index-based).
    Fallback: name-based walk up 3 ancestor levels.
    """
    clicked = await page.evaluate("""
        (function(targetIdx) {
            const isAdd = b => b.innerText.trim().toUpperCase() === 'ADD';
            const allAdds = [...document.querySelectorAll('button,[role="button"]')]
                .filter(isAdd);
            if (!allAdds.length) return false;

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
