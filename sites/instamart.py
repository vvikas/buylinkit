from playwright.async_api import Page
from agent import do

START_URL = "https://www.swiggy.com/instamart"


async def search_raw(page: Page, query: str) -> str:
    if "swiggy.com" not in page.url:
        await page.goto(START_URL, timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=20000)

    await do(page, f"Search for '{query}' — click the search bar, type the query, press Enter, and wait for results to load. Return done when you see product cards with prices.", "instamart")
    await page.wait_for_load_state("domcontentloaded", timeout=15000)
    await page.wait_for_timeout(3000)
    return await page.inner_text("body")


async def add_to_cart(page: Page, product_name: str, product_index: int = 0) -> bool:
    await do(page, f'Click the ADD button at index {product_index} (0-based). Use {{"click": "ADD", "nth": {product_index}}} then return done.', "instamart", max_steps=1)
    return True
