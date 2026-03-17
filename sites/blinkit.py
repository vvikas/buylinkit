from urllib.parse import quote
from playwright.async_api import Page
from sites.session import click_add_button

SEARCH_URL = "https://blinkit.com/s/?q={}"
CART_URL   = "https://blinkit.com/cart"


async def search_raw(page: Page, query: str) -> str:
    """Navigate to search URL and return raw page text. No prompting."""
    url = SEARCH_URL.format(quote(query))
    await page.goto(url, timeout=20000)
    await page.wait_for_load_state("networkidle", timeout=15000)
    await page.wait_for_timeout(2000)
    return await page.inner_text("body")


# kept for backward compat if called directly
search = search_raw


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
