from playwright.async_api import Page
from agent import do

START_URL = "https://blinkit.com"


async def search_raw(page: Page, query: str) -> str:
    if "blinkit.com" not in page.url:
        await page.goto(START_URL, timeout=20000)
        await page.wait_for_load_state("domcontentloaded", timeout=15000)

    await do(page, f"Search for '{query}'. Step by step: 1) click any 'Search \"...\"' text to open search. 2) type '{query}'. 3) press Enter. Return done when the URL contains '/s/' indicating search results loaded.", "blinkit")
    await page.wait_for_load_state("networkidle", timeout=12000)
    await page.wait_for_timeout(2000)
    return await page.inner_text("body")


async def add_to_cart(page: Page, product_name: str, product_index: int = 0) -> bool:
    # Count how many products before this index are already in cart (no ADD button).
    # Their ADD is replaced by a quantity number, shifting the nth index.
    import re
    page_text = await page.inner_text("body")
    # Blinkit pattern: each product has either "ADD" or a digit (qty) as the action button
    # Find markers that appear on their own line right before or after price lines
    markers = re.findall(r'\n(ADD|\d+)\n', page_text)
    already_in_cart = 0
    for i, marker in enumerate(markers):
        if i >= product_index:
            break
        if marker != "ADD":
            already_in_cart += 1

    # If the item itself is already in cart, skip the ADD click
    if product_index < len(markers) and markers[product_index] != "ADD":
        print(f"  [blinkit] item already in cart (qty: {markers[product_index]}), skipping ADD")
    else:
        adjusted_nth = product_index - already_in_cart
        await do(page, f'Click the ADD button at index {adjusted_nth} (0-based). Use {{"click": "ADD", "nth": {adjusted_nth}}} then return done.', "blinkit", max_steps=1)

    return True
