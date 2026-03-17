from playwright.async_api import Page
from agent import do

START_URL = "https://www.zepto.com"


async def search_raw(page: Page, query: str) -> str:
    # Zepto's home page search is an <a> link that navigates to /search
    # Go directly to the search page where the input is available
    if "/search" not in page.url:
        await page.goto("https://www.zepto.com/search", timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=20000)
        await page.wait_for_timeout(1500)

    await do(page, f"Search for '{query}'. The search input has placeholder 'Search for over 5000 products'. Click it if not focused, type '{query}', press Enter. Return done when you see product results for the query.", "zepto")
    await page.wait_for_load_state("domcontentloaded", timeout=15000)
    await page.wait_for_timeout(3000)
    return await page.inner_text("body")


async def add_to_cart(page: Page, product_name: str, product_index: int = 0) -> bool:
    # Count how many products before this index are already in cart (no ADD button).
    # Their ADD is replaced by a quantity number, shifting the nth index.
    page_text = await page.inner_text("body")
    # Parse product blocks: each product starts with either "ADD" or a number (quantity)
    # followed by ₹price. Count non-ADD entries before product_index.
    import re
    # Find all product-card markers: "ADD\n₹" or "<digit>\n₹"
    markers = re.findall(r'^(ADD|\d+)\n₹', page_text, re.MULTILINE)
    already_in_cart = 0
    for i, marker in enumerate(markers):
        if i >= product_index:
            break
        if marker != "ADD":
            already_in_cart += 1

    # If the item itself is already in cart, skip the ADD click
    if product_index < len(markers) and markers[product_index] != "ADD":
        print(f"  [zepto] item already in cart (qty: {markers[product_index]}), skipping ADD")
    else:
        adjusted_nth = product_index - already_in_cart
        await do(page, f'Click the ADD button at index {adjusted_nth} (0-based). Use {{"click": "ADD", "nth": {adjusted_nth}}} then return done.', "zepto", max_steps=1)

    return True
