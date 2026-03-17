"""
LLM-powered product extraction from page text.
All browser navigation logic has moved to agent.py.
"""

import os
import json
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None

HINTS_DIR = Path(__file__).parent / "sites" / "hints"


def _get_client() -> Groq:
    global _client
    if _client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set — copy .env.example to .env and add your key")
        _client = Groq(api_key=key)
    return _client


def _model() -> str:
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _load_hint(site: str) -> str:
    """Load the extraction-relevant section from the site hint file."""
    path = HINTS_DIR / f"{site.lower()}.md"
    if path.exists():
        return path.read_text()
    return ""


def extract_products(page_text: str, query: str, site: str) -> list[dict]:
    client = _get_client()
    hint = _load_hint(site)
    try:
        resp = client.chat.completions.create(
            model=_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract the top 5 grocery products matching the query from raw website text.\n"
                        "Return JSON: {\"products\": [{\"name\": str, \"price\": int, \"unit\": str, "
                        "\"available\": bool, \"delivery_mins\": int|null}]}\n"
                        "price = INR integer. available=false only if out of stock or 'Notify Me'.\n"
                        "delivery_mins: minutes from delivery promise text, else null.\n"
                        + (f"\n## Site hints\n{hint}" if hint else "")
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
