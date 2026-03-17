from urllib.parse import quote
from playwright.async_api import Page
from sites.session import ensure_location, click_add_button

SEARCH_URL = "https://www.swiggy.com/instamart/search?query={}"
CART_URL   = "https://www.swiggy.com/instamart"
WINDOW_POS = (760, 40)


async def search(page: Page, query: str) -> str:
    url = SEARCH_URL.format(quote(query))
    await page.goto(url, timeout=30000)
    await page.wait_for_load_state("domcontentloaded", timeout=20000)
    await page.wait_for_timeout(3000)
    text = await page.inner_text("body")
    return await ensure_location(page, text, "Instamart")


async def add_to_cart(page: Page, product_name: str,
                      product_index: int = 0) -> bool:
    clicked = await click_add_button(page, product_name, product_index)
    if clicked:
        await page.wait_for_timeout(1500)
        await page.goto(CART_URL, timeout=20000)
        await page.wait_for_timeout(2000)
    return clicked
