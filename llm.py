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


_SITE_HINTS = {
    "Zepto": (
        "IMPORTANT — Zepto page text format: each product block looks like:\n"
        "  ADD\n  ₹<selling_price>\n  ₹<MRP>\n  ₹<discount>\n  OFF\n  <product name>\n  <unit>\n"
        "The FIRST ₹ after ADD is the selling price. The product name comes AFTER 'OFF'. "
        "All products shown this way ARE available (they have an ADD button). "
        "Only mark available: false if you see 'Notify Me' or 'Out of Stock' instead of ADD."
    ),
    "Instamart": (
        "This is Swiggy Instamart. Products listed with name, weight/unit, price. "
        "Look for 'ADD' buttons near products — those are available. "
        "delivery_mins: Swiggy often shows '10 mins' or similar near the top of the page — use that for all products if present."
    ),
}


def extract_products(page_text: str, query: str, site: str) -> list[dict]:
    """Extract product listings with prices from raw scraped page text."""
    client = _get_client()
    truncated = page_text[:6000]
    site_hint = _SITE_HINTS.get(site, "")
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract grocery product listings from raw website text. "
                        "Return a JSON object with key 'products' — an array of the top 5 "
                        "most relevant matches for the query. Each item: "
                        "{\"name\": str, \"price\": int, \"unit\": str, \"available\": bool, \"delivery_mins\": int | null}. "
                        "price is INR as integer (no ₹ symbol). unit is pack size e.g. '1 kg', '500 g', '6 pack'. "
                        "Set available: false if out of stock or shows 'notify me'. "
                        "delivery_mins: extract the promised delivery time in minutes if shown (e.g. '8 mins' → 8, '10-12 mins' → 11), else null. "
                        + (f"\n\n{site_hint}" if site_hint else "") +
                        "\n\nReturn only valid JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Site: {site}\nQuery: {query}\n\nPage text:\n{truncated}",
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=600,
            temperature=0.1,
        )
        data = json.loads(resp.choices[0].message.content)
        return data.get("products", [])
    except Exception as e:
        print(f"[{site}] LLM extraction error: {e}")
        return []
