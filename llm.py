import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set — copy .env.example to .env and add your key")
        _client = Groq(api_key=key)
    return _client


# ── Product extraction ──────────────────────────────────────────────────────

_SITE_HINTS = {
    "Zepto": (
        "Zepto page text format: each product block looks like:\n"
        "  ADD\n  ₹<selling_price>\n  ₹<MRP>\n  <discount>% OFF\n  <product name>\n  <unit>\n"
        "The FIRST ₹ after ADD is the selling price. "
        "Products with ADD button ARE available. Only mark available:false if you see 'Notify Me'."
    ),
    "Instamart": (
        "This is Swiggy Instamart. Products listed with name, weight/unit, price. "
        "ADD buttons near products = available. "
        "delivery_mins: Swiggy often shows '10 mins' near the top — use that for all."
    ),
}


def extract_products(page_text: str, query: str, site: str) -> list[dict]:
    client = _get_client()
    hint = _SITE_HINTS.get(site, "")
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract the top 5 grocery products matching the query from raw website text.\n"
                        "Return JSON: {\"products\": [{\"name\": str, \"price\": int, \"unit\": str, "
                        "\"available\": bool, \"delivery_mins\": int|null}]}\n"
                        "price = INR integer. available=false only if out of stock or 'Notify Me'.\n"
                        "delivery_mins: minutes from delivery promise text, else null.\n"
                        + (f"\n{hint}" if hint else "")
                    ),
                },
                {"role": "user", "content": f"Site: {site}\nQuery: {query}\n\n{page_text[:6000]}"},
            ],
            response_format={"type": "json_object"},
            max_tokens=600,
            temperature=0.1,
        )
        return json.loads(resp.choices[0].message.content).get("products", [])
    except Exception as e:
        print(f"[{site}] extraction error: {e}")
        return []


# ── General-purpose LLM browser agent ──────────────────────────────────────

def _decide(page_text: str, url: str, goal: str, site: str) -> dict:
    """
    Ask the LLM for ONE next action toward the goal.

    Returns one of:
      {"click": "visible text"}
      {"fill": "placeholder or label text", "value": "text to type"}
      {"press": "Enter"}
      {"done": true}
      {"wait_user": "message for user"}
      {"give_up": "reason"}
    """
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You control a real browser on {site}. Goal: {goal}\n\n"
                        "Return exactly ONE action as JSON:\n"
                        '  {"click": "visible button or link text"}  — click by visible text\n'
                        '  {"fill": "placeholder/label text", "value": "text"}  — fill input\n'
                        '  {"press": "Enter"}  — press a key\n'
                        '  {"done": true}  — goal is achieved\n'
                        '  {"wait_user": "tell user what to do in browser then press Enter"}\n'
                        '  {"give_up": "reason"}\n\n'
                        "Prefer click/fill over give_up. Be specific with text.\n"
                        f"Current URL: {url}"
                    ),
                },
                {"role": "user", "content": f"Page content:\n{page_text[:4000]}"},
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"give_up": "LLM error"}


async def _execute(page, action: dict) -> bool:
    """Execute a single action dict on the page. Returns True if something was done."""
    from playwright.async_api import TimeoutError as PWTimeout

    if action.get("done") or action.get("give_up") or action.get("wait_user"):
        return False

    # click
    if "click" in action:
        text = action["click"]
        # Try by text
        for attempt in [
            lambda: page.get_by_text(text, exact=True).first,
            lambda: page.get_by_text(text, exact=False).first,
            lambda: page.get_by_role("button", name=text).first,
            lambda: page.get_by_role("link", name=text).first,
        ]:
            try:
                loc = attempt()
                if await loc.is_visible(timeout=2000):
                    await loc.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    await page.wait_for_timeout(1500)
                    return True
            except Exception:
                continue
        return False

    # fill
    if "fill" in action and "value" in action:
        placeholder = action["fill"]
        value = action["value"]
        for attempt in [
            lambda: page.get_by_placeholder(placeholder, exact=False).first,
            lambda: page.get_by_label(placeholder, exact=False).first,
            lambda: page.locator(f'input[placeholder*="{placeholder}" i]').first,
            lambda: page.locator('input[type="tel"]').first,
            lambda: page.locator('input[type="text"]').first,
        ]:
            try:
                loc = attempt()
                if await loc.is_visible(timeout=2000):
                    await loc.click()
                    await loc.fill(value)
                    await page.wait_for_timeout(500)
                    return True
            except Exception:
                continue
        return False

    # press
    if "press" in action:
        await page.keyboard.press(action["press"])
        await page.wait_for_timeout(1500)
        return True

    return False


async def act(page, goal: str, site: str, max_steps: int = 8) -> str:
    """
    Drive the browser toward `goal` using LLM decisions.

    Returns:
      "done"      — goal achieved
      "wait_user" — paused, caller should prompt user then continue
      "gave_up"   — LLM gave up
    """
    for step in range(max_steps):
        await page.wait_for_timeout(800)
        try:
            page_text = await page.inner_text("body")
        except Exception:
            page_text = ""

        action = _decide(page_text, page.url, goal, site)

        if action.get("done"):
            return "done"

        if action.get("wait_user"):
            # Caller handles the user prompt
            action["_message"] = action.get("wait_user", "Take action in browser then press Enter.")
            # Store on page object so caller can read it — simpler: just raise
            raise _WaitUser(action["_message"])

        if action.get("give_up"):
            return "gave_up"

        await _execute(page, action)

    return "gave_up"


class _WaitUser(Exception):
    """Raised by act() when user interaction is needed (e.g. enter OTP)."""
    pass


# Expose so main.py can catch it
WaitUser = _WaitUser


# ── Cart navigation (LLM-driven) ────────────────────────────────────────────

_CART_PATTERNS = ["cart", "checkout", "bag", "payment", "order-summary"]


def _on_cart_page(url: str) -> bool:
    u = url.lower()
    return any(p in u for p in _CART_PATTERNS)


async def navigate_to_cart(page, site: str) -> bool:
    """After clicking ADD, let the LLM navigate to the cart/checkout page."""
    if _on_cart_page(page.url):
        return True
    try:
        result = await act(
            page,
            goal="An item was just added to cart. Navigate to the cart or checkout page. "
                 "Look for 'View Cart', 'Go to Cart', cart icon with item count, 'Proceed', etc.",
            site=site,
            max_steps=6,
        )
        return result == "done" or _on_cart_page(page.url)
    except _WaitUser:
        return _on_cart_page(page.url)
