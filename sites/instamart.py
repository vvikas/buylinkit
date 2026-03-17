from playwright.async_api import Page
from sites.session import click_add_button, do_search
from llm import navigate_to_cart

START_URL = "https://www.swiggy.com/instamart"


async def search_raw(page: Page, query: str) -> str:
    if "swiggy.com" not in page.url:
        await page.goto(START_URL, timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

    await do_search(page, query, "Instamart")
    await page.wait_for_load_state("domcontentloaded", timeout=15000)
    await page.wait_for_timeout(3000)
    return await page.inner_text("body")


async def add_to_cart(page: Page, product_name: str, product_index: int = 0) -> bool:
    clicked = await click_add_button(page, product_name, product_index)
    if not clicked:
        return False
    return await navigate_to_cart(page, "Instamart")
