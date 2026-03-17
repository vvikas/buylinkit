from urllib.parse import quote
from playwright.async_api import Page
from sites.session import ensure_location, click_add_button

SEARCH_URL = "https://www.zepto.com/search?query={}"
CART_URL   = "https://www.zepto.com/cart"
WINDOW_POS = (730, 20)


async def search(page: Page, query: str) -> str:
    url = SEARCH_URL.format(quote(query))
    await page.goto(url, timeout=30000)
    await page.wait_for_load_state("domcontentloaded", timeout=20000)
    await page.wait_for_timeout(4000)
    text = await page.inner_text("body")
    return await ensure_location(page, text, "Zepto")


async def add_to_cart(page: Page, product_name: str,
                      product_index: int = 0) -> bool:
    clicked = await click_add_button(page, product_name, product_index)
    if clicked:
        await page.wait_for_timeout(1500)
        await page.goto(CART_URL, timeout=20000)
        await page.wait_for_timeout(2000)
    return clicked
