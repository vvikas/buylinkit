"""
BrowserSession — owns the playwright + context lifecycle for one site.
All site modules use this to open/close their browser; main.py keeps
sessions alive across search -> add-to-cart so windows never reopen.
"""
import subprocess
from pathlib import Path
from playwright.async_api import Page


def _get_screen_size():
    """Return (width, height) logical pixels of the primary display on macOS."""
    try:
        out = subprocess.check_output(
            ["osascript", "-e",
             "tell application \"Finder\" to get bounds of window of desktop"],
            text=True, timeout=3,
        ).strip()  # "0, 0, 1440, 900"
        parts = [int(x.strip()) for x in out.split(",")]
        return parts[2], parts[3]
    except Exception:
        return 1440, 900  # sensible fallback

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
    def __init__(self, site_key: str, position=None, size=None):
        """
        position: (x, y) logical pixels for window placement, or None for OS default.
        size:     (w, h) logical pixels for window size, or None for OS default.
        """
        self.site_key  = site_key
        self.position  = position
        self.size      = size
        self._profile  = str(PROFILE_DIR / site_key)
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
        args = ["--disable-blink-features=AutomationControlled"]
        if self.position:
            args.append(f"--window-position={self.position[0]},{self.position[1]}")
        if self.size:
            args.append(f"--window-size={self.size[0]},{self.size[1]}")
        self._ctx = await self._pw.chromium.launch_persistent_context(
            self._profile,
            headless=False,
            user_agent=self._USER_AGENT,
            args=args,
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
        await self._ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return self._page

    async def bring_to_front(self):
        """Move browser window on-screen and bring to front."""
        if self._page:
            await self._page.evaluate("window.moveTo(100, 100)")
            await self._page.bring_to_front()

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
                setattr(self, attr, None)
        self._page = None


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
