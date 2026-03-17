from urllib.parse import quote
from playwright.async_api import Page
from sites.session import click_add_button

SEARCH_URL = "https://www.swiggy.com/instamart/search?query={}"
CART_URL   = "https://www.swiggy.com/instamart"


async def search_raw(page: Page, query: str) -> str:
    """Navigate to search URL and return raw page text. No prompting."""
    url = SEARCH_URL.format(quote(query))
    await page.goto(url, timeout=30000)
    await page.wait_for_load_state("domcontentloaded", timeout=20000)
    await page.wait_for_timeout(3000)
    return await page.inner_text("body")


search = search_raw


async def add_to_cart(page: Page, product_name: str,
                      product_index: int = 0) -> bool:
    clicked = await click_add_button(page, product_name, product_index)
    if clicked:
        await page.wait_for_timeout(1500)
        await page.goto(CART_URL, timeout=20000)
        await page.wait_for_timeout(2000)
    return clicked
