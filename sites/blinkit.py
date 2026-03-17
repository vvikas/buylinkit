from playwright.async_api import Page
from sites.session import click_add_button
from llm import act, navigate_to_cart

START_URL = "https://blinkit.com"


async def login_sequence(page: Page, phone: str) -> bool:
    """
    Blinkit login: click Login → fill phone → click Continue/Get OTP.
    Returns True if OTP was triggered.
    """
    if "blinkit.com" not in page.url:
        await page.goto(START_URL, timeout=20000)
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)

    # Click Login button — try common text variants
    for text in ["Login", "Sign In", "Log in", "Sign in"]:
        try:
            loc = page.get_by_text(text, exact=True).first
            if await loc.is_visible(timeout=2000):
                await loc.click()
                await page.wait_for_timeout(1500)
                break
        except Exception:
            continue

    # Fill phone — Blinkit uses type="tel"
    phone_input = None
    for sel in ['input[type="tel"]', 'input[placeholder*="phone" i]',
                'input[placeholder*="mobile" i]', 'input[placeholder*="number" i]']:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=2000):
                phone_input = loc
                break
        except Exception:
            continue

    if phone_input is None:
        return False

    # Click, wait for focus, then type character by character
    await phone_input.click()
    await page.wait_for_timeout(600)   # wait for any JS focus handlers to fire
    await phone_input.fill("")         # clear first
    await phone_input.type(phone, delay=60)   # type slowly — triggers input events
    await page.wait_for_timeout(400)

    # Click OTP button
    for text in ["Continue", "Get OTP", "Send OTP", "Request OTP", "Login"]:
        try:
            loc = page.get_by_role("button", name=text).first
            if await loc.is_visible(timeout=2000):
                await loc.click()
                return True
        except Exception:
            continue

    await page.keyboard.press("Enter")
    return True


async def search_raw(page: Page, query: str) -> str:
    if "blinkit.com" not in page.url:
        await page.goto(START_URL, timeout=20000)
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)

    await act(
        page,
        goal=f"Find the search box and search for '{query}'. "
             "Click the search input, type the query, then press Enter or click Search.",
        site="Blinkit",
        max_steps=5,
    )
    await page.wait_for_load_state("networkidle", timeout=12000)
    await page.wait_for_timeout(2000)
    return await page.inner_text("body")


async def add_to_cart(page: Page, product_name: str, product_index: int = 0) -> bool:
    clicked = await click_add_button(page, product_name, product_index)
    if not clicked:
        return False
    return await navigate_to_cart(page, "Blinkit")
