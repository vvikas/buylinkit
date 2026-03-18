"""
Unified LLM browser agent.

One function — do() — drives any action on any site.
Reads static site hints (.md) + live DOM text, asks the LLM for one action,
Playwright executes it. No screenshots, no CSS selectors, no JS hacks.
"""

import os
import json
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None
_hints_cache: dict[str, str] = {}

HINTS_DIR = Path(__file__).parent / "sites" / "hints"


def _get_client() -> Groq:
    global _client
    if _client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set")
        _client = Groq(api_key=key)
    return _client


def _model() -> str:
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _load_hints(site: str) -> str:
    """Load and cache the site hint markdown file."""
    if site not in _hints_cache:
        path = HINTS_DIR / f"{site}.md"
        if path.exists():
            _hints_cache[site] = path.read_text()
        else:
            _hints_cache[site] = ""
    return _hints_cache[site]


def _decide(page_text: str, url: str, goal: str, site: str, history=None) -> dict:
    """
    Ask the LLM for ONE next action.

    Returns one of:
      {"click": "visible text on the element to click"}
      {"type": "text to type"}              — types into the currently focused input
      {"press": "Enter"}                    — press a key
      {"goto": "https://..."}               — navigate to URL
      {"done": true}                        — goal achieved
      {"give_up": "reason"}
    """
    client = _get_client()
    hints = _load_hints(site)

    system = (
        f"You are a browser automation agent on {site}.\n\n"
        f"## Site Knowledge\n{hints}\n\n"
        f"## Current State\nURL: {url}\n\n"
        "## Your Task\n"
        f"{goal}\n\n"
        "## Actions\n"
        "Return exactly ONE action as JSON. Examples:\n"
        '  {"click": "Search", "nth": 0}  — click element by visible text; nth is 0-based index for repeated elements\n'
        '  {"type": "milk"}  — type this exact string into the focused input, nothing else\n'
        '  {"press": "Enter"}  — press a keyboard key\n'
        '  {"goto": "https://example.com"}  — navigate to URL\n'
        '  {"done": true}  — goal achieved\n'
        '  {"give_up": "reason"}\n\n'
        "CRITICAL: The \"type\" value must contain ONLY the text to type. No descriptions, no extra words.\n\n"
        "Rules:\n"
        "- Use click to interact with buttons, links, search bars, etc.\n"
        "- IMPORTANT: After clicking a search bar or input, the next action MUST be type. Do NOT click again.\n"
        "- IMPORTANT: After typing into a search box, the next action MUST be press Enter. Do NOT click.\n"
        "- Use goto only when you know the exact URL (e.g. cart URL from site knowledge).\n"
        "- Return done when the page state shows the goal is achieved.\n"
        "- Be precise with click text — use the exact text visible on the element.\n"
        "- Only return ONE action per response. Follow the sequence: click → type → press Enter.\n"
    )

    if history:
        lines = "\n".join(f"  {i+1}. {json.dumps(a, ensure_ascii=False)}" for i, a in enumerate(history))
        system += (
            f"\n## Previous Actions (already executed)\n{lines}\n"
            "→ Do NOT repeat any of these. Pick the NEXT logical action.\n"
        )

    try:
        resp = client.chat.completions.create(
            model=_model(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Page text (first 4000 chars):\n{page_text[:4000]}"},
            ],
            response_format={"type": "json_object"},
            max_tokens=150,
            temperature=0,
        )
        parsed = json.loads(resp.choices[0].message.content)
        # LLM sometimes returns a list — extract the first dict with an action
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and item:
                    parsed = item
                    break
            else:
                parsed = {"give_up": "LLM returned empty list"}
        if not isinstance(parsed, dict):
            parsed = {"give_up": "LLM returned non-dict"}
        return parsed
    except Exception as e:
        print(f"[{site}] agent LLM error: {e}")
        return {"give_up": "LLM error"}


async def _execute(page, action: dict) -> bool:
    """Execute one action on the page. Returns True if something was done."""
    if action.get("done") or action.get("give_up"):
        return False

    # goto — direct navigation
    if "goto" in action:
        try:
            await page.goto(action["goto"], timeout=15000)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            await page.wait_for_timeout(1500)
            return True
        except Exception:
            return False

    # click — find element by visible text, with optional nth index
    if "click" in action:
        text = action["click"]
        nth = action.get("nth", 0)  # 0-based index for repeated elements
        for attempt in [
            lambda: page.get_by_placeholder(text, exact=False),
            lambda: page.get_by_role("button", name=text),
            lambda: page.get_by_role("link", name=text),
            lambda: page.get_by_text(text, exact=True),
            lambda: page.get_by_text(text, exact=False),
        ]:
            try:
                loc = attempt()
                if nth > 0:
                    loc = loc.nth(nth)
                else:
                    loc = loc.first
                if await loc.is_visible(timeout=3000):
                    await loc.click()
                    await page.wait_for_timeout(1000)
                    return True
            except Exception:
                continue
        print(f"  click failed: could not find '{text}' (nth={nth})")
        return False

    # type — into currently focused element
    if "type" in action:
        try:
            await page.keyboard.type(action["type"], delay=60)
            await page.wait_for_timeout(400)
            return True
        except Exception:
            return False

    # press — keyboard key
    if "press" in action:
        try:
            await page.keyboard.press(action["press"])
            await page.wait_for_timeout(1500)
            return True
        except Exception:
            return False

    return False


async def do(page, goal: str, site: str, max_steps: int = 5) -> str:
    """
    Drive the browser toward `goal` using LLM decisions + site hints.

    Returns: "done" | "gave_up"
    """
    history: list[dict] = []
    for step in range(max_steps):
        await page.wait_for_timeout(800)

        try:
            page_text = await page.inner_text("body")
        except Exception:
            page_text = ""

        # Add focused element info so LLM knows when to type vs click
        try:
            focused = await page.evaluate("""() => {
                const el = document.activeElement;
                if (!el || el === document.body) return null;
                return {tag: el.tagName, type: el.type || null, placeholder: el.placeholder || null};
            }""")
            if focused and focused.get("tag") in ("INPUT", "TEXTAREA"):
                page_text = f"[FOCUSED: {focused['tag']} type={focused.get('type')} placeholder={focused.get('placeholder', '')}]\n\n" + page_text
        except Exception:
            pass

        action = _decide(page_text, page.url, goal, site, history)
        if os.getenv("BUYLINKIT_VERBOSE"):
            print(f"  [{site}] step {step+1}: {json.dumps(action, ensure_ascii=False)}")

        if action.get("done"):
            return "done"
        if action.get("give_up"):
            print(f"  [{site}] gave up: {action['give_up']}")
            return "gave_up"

        await _execute(page, action)
        history.append(action)

    return "gave_up"
