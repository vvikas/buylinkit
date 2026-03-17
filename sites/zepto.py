from playwright.async_api import Page
from sites.session import click_add_button
from llm import act, navigate_to_cart

START_URL = "https://www.zepto.com"


async def login_sequence(page: Page, phone: str) -> bool:
    """
    Zepto login: click Login → fill mobile → click Get OTP.
    """
    if "zepto.com" not in page.url:
        await page.goto(START_URL, timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

    for text in ["Login", "Sign In", "Log in", "Sign in", "Get Started"]:
        try:
            loc = page.get_by_text(text, exact=True).first
            if await loc.is_visible(timeout=2000):
                await loc.click()
                await page.wait_for_timeout(1500)
                break
        except Exception:
            continue

    # Zepto uses type="tel" or placeholder "Enter mobile number"
    phone_input = None
    for sel in ['input[type="tel"]', 'input[placeholder*="mobile" i]',
                'input[placeholder*="phone" i]', 'input[placeholder*="number" i]',
                'input[type="text"]']:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=2000):
                phone_input = loc
                break
        except Exception:
            continue

    if phone_input is None:
        return False

    await phone_input.click()
    await page.wait_for_timeout(600)
    await phone_input.fill("")
    await phone_input.type(phone, delay=60)
    await page.wait_for_timeout(400)

    for text in ["Get OTP", "Continue", "Send OTP", "Request OTP", "Login"]:
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
    if "zepto.com" not in page.url:
        await page.goto(START_URL, timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

    await act(
        page,
        goal=f"Find the search box and search for '{query}'. "
             "Click the search input, type the query, then press Enter or click Search.",
        site="Zepto",
        max_steps=5,
    )
    await page.wait_for_load_state("domcontentloaded", timeout=15000)
    await page.wait_for_timeout(3000)
    return await page.inner_text("body")


async def add_to_cart(page: Page, product_name: str, product_index: int = 0) -> bool:
    clicked = await click_add_button(page, product_name, product_index)
    if not clicked:
        return False
    return await navigate_to_cart(page, "Zepto")
