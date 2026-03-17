from urllib.parse import quote
from playwright.async_api import Page
from sites.session import ensure_location, click_add_button

SEARCH_URL = "https://blinkit.com/s/?q={}"
CART_URL   = "https://blinkit.com/cart"
WINDOW_POS = (700, 0)   # x, y — sits on the right, terminal stays visible


async def search(page: Page, query: str) -> str:
    """Navigate to search results and return page body text."""
    url = SEARCH_URL.format(quote(query))
    await page.goto(url, timeout=20000)
    await page.wait_for_load_state("networkidle", timeout=15000)
    await page.wait_for_timeout(2000)
    text = await page.inner_text("body")
    return await ensure_location(page, text, "Blinkit")


async def add_to_cart(page: Page, product_name: str,
                      product_index: int = 0) -> bool:
    """
    Add product to cart using the already-open search results page.
    No browser reopening — page stays alive from the search step.
    Returns True if ADD was clicked successfully.
    """
    clicked = await click_add_button(page, product_name, product_index)
    if clicked:
        await page.wait_for_timeout(1500)
        await page.goto(CART_URL, timeout=15000)
        await page.wait_for_timeout(2000)
    return clicked
