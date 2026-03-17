from playwright.async_api import Page
from sites.session import click_add_button
from llm import act, navigate_to_cart

START_URL = "https://www.swiggy.com/instamart"


async def login_sequence(page: Page, phone: str) -> bool:
    """
    Swiggy Instamart login.

    Swiggy's modal uses a plain <input type="text"> (not type="tel"),
    positioned inside a dynamically injected overlay. We must:
      1. Click the Sign In / Login button in the header.
      2. Wait for the modal to appear (up to 3 s).
      3. Find the phone input inside the modal.
      4. Fill number and click Login.
    """
    if "swiggy.com" not in page.url:
        await page.goto(START_URL, timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

    # Step 1 — click Login/Sign In in the header
    clicked_login = False
    for text in ["Sign In", "Login", "Log In", "Sign in", "Log in"]:
        try:
            loc = page.get_by_text(text, exact=True).first
            if await loc.is_visible(timeout=2000):
                await loc.click()
                await page.wait_for_timeout(2500)   # wait for modal animation
                clicked_login = True
                break
        except Exception:
            continue

    if not clicked_login:
        # LLM fallback — try to find the login trigger
        try:
            await act(
                page,
                goal="Find and click the Login or Sign In button to open the login modal.",
                site="Instamart",
                max_steps=3,
            )
            await page.wait_for_timeout(2500)
        except Exception:
            pass

    # Step 2 — find the phone input inside the modal
    # Swiggy uses type="text" inside a modal div; try selectors from most to least specific
    phone_input = None
    for sel in [
        'input[type="tel"]',
        'input[placeholder*="mobile" i]',
        'input[placeholder*="phone" i]',
        'input[placeholder*="number" i]',
        'input[placeholder*="enter" i]',
        'input[type="number"]',
        'input[type="text"]',           # Swiggy often uses plain text input
    ]:
        try:
            # Look inside any open modal/dialog first
            for container_sel in ['[role="dialog"]', '[class*="modal" i]',
                                   '[class*="login" i]', '[class*="auth" i]', 'body']:
                loc = page.locator(container_sel).locator(sel).first
                if await loc.is_visible(timeout=1500):
                    phone_input = loc
                    break
            if phone_input:
                break
        except Exception:
            continue

    if phone_input is None:
        return False

    # Step 3 — fill phone number
    await phone_input.click()
    await page.wait_for_timeout(600)   # wait for JS focus handlers
    await phone_input.fill("")
    await phone_input.type(phone, delay=60)
    await page.wait_for_timeout(500)

    # Step 4 — click Login / Continue button inside the modal
    for text in ["Login", "Continue", "Get OTP", "Send OTP", "Request OTP", "Proceed"]:
        try:
            for container_sel in ['[role="dialog"]', '[class*="modal" i]',
                                   '[class*="login" i]', 'body']:
                loc = (page.locator(container_sel)
                           .get_by_role("button", name=text).first)
                if await loc.is_visible(timeout=2000):
                    await loc.click()
                    return True
        except Exception:
            continue

    # Last resort — Enter key
    await phone_input.press("Enter")
    return True


async def search_raw(page: Page, query: str) -> str:
    if "swiggy.com" not in page.url:
        await page.goto(START_URL, timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

    await act(
        page,
        goal=f"Find the search box and search for '{query}'. "
             "Click the search input, type the query, then press Enter or click Search.",
        site="Instamart",
        max_steps=5,
    )
    await page.wait_for_load_state("domcontentloaded", timeout=15000)
    await page.wait_for_timeout(3000)
    return await page.inner_text("body")


async def add_to_cart(page: Page, product_name: str, product_index: int = 0) -> bool:
    clicked = await click_add_button(page, product_name, product_index)
    if not clicked:
        return False
    return await navigate_to_cart(page, "Instamart")
