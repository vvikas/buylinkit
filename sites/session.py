"""
BrowserSession — owns the playwright + context lifecycle for one site.
All site modules use this to open/close their browser; main.py keeps
sessions alive across search → add-to-cart so windows never reopen.
"""
import os
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
    """
    Manages one persistent Chromium profile for one site.
    Call await session.start() to open the browser and get the page.
    Call await session.close() when done.
    """

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

    # Real Chrome 124 UA — prevents sites (especially Swiggy) from detecting
    # Playwright's Chromium as a bot.
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
                "--disable-blink-features=AutomationControlled",  # hides navigator.webdriver
            ],
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
        # Remove the webdriver property that sites check for bot detection
        await self._ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
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
# Detection helpers — pure functions, no prompting (main.py handles that)
# ---------------------------------------------------------------------------

def needs_login(page_text: str, site: str, url: str = "") -> bool:
    """True if the page is a login wall — checks URL first (most reliable)."""
    # URL redirect is the strongest signal
    url_lower = url.lower()
    if any(x in url_lower for x in ["login", "signin", "sign-in", "/auth"]):
        return True
    text_lower = page_text.lower()[:800]
    signals    = _LOGIN_SIGNALS.get(site, [])
    has_login  = any(s in text_lower for s in signals)
    has_prices = "₹" in page_text[:3000]
    return has_login and not has_prices


def needs_location(page_text: str, site: str) -> bool:
    """True if prices are absent because no delivery location is set."""
    text_lower = page_text.lower()
    signals    = _NO_LOCATION_SIGNALS.get(site, [])
    has_signal = any(s in text_lower[:500] for s in signals)
    has_prices = "₹" in text_lower[:2000]
    return has_signal and not has_prices


# ---------------------------------------------------------------------------
# Auto-login: fill phone number and trigger OTP
# ---------------------------------------------------------------------------

# Ordered list of selectors to try for the phone input field
_PHONE_SELECTORS = [
    'input[type="tel"]',
    'input[placeholder*="mobile" i]',
    'input[placeholder*="phone" i]',
    'input[placeholder*="number" i]',
    'input[name*="mobile" i]',
    'input[name*="phone" i]',
]

# Ordered list of selectors to try for the "send OTP" button
_OTP_BTN_SELECTORS = [
    'button:has-text("Get OTP")',
    'button:has-text("Send OTP")',
    'button:has-text("Request OTP")',
    'button:has-text("Continue")',
    'button[type="submit"]',
]


async def auto_fill_phone(page: Page, site: str = "") -> bool:
    """
    1. Use LLM to click the Login/Sign-in button (opens login form if hidden).
    2. Fill PHONE_NUMBER from env into the phone input.
    3. Click the OTP button / press Enter.
    Returns True if phone was filled and OTP triggered.
    """
    phone = os.getenv("PHONE_NUMBER", "").strip()
    if not phone:
        return False

    # Step 1 — LLM navigates to the login form (click Login button if needed)
    try:
        from llm import act
        await act(
            page,
            goal="Find and click the Login or Sign In button to open the phone number login form.",
            site=site or "the site",
            max_steps=4,
        )
        await page.wait_for_timeout(1500)
    except Exception:
        pass  # If login form is already visible or LLM gave up, continue anyway

    try:
        # Step 2 — find visible phone input
        phone_input = None
        for sel in _PHONE_SELECTORS:
            loc = page.locator(sel).first
            try:
                if await loc.is_visible(timeout=2000):
                    phone_input = loc
                    break
            except Exception:
                continue

        if phone_input is None:
            return False

        await phone_input.click()
        await phone_input.fill("")
        await phone_input.type(phone, delay=40)
        await page.wait_for_timeout(400)

        # Step 3 — click OTP button
        for sel in _OTP_BTN_SELECTORS:
            loc = page.locator(sel).first
            try:
                if await loc.is_visible(timeout=2000):
                    await loc.click()
                    return True
            except Exception:
                continue

        # Fallback: Enter key
        await phone_input.press("Enter")
        return True

    except Exception:
        return False


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
