import asyncio
import argparse

from sites import blinkit, zepto, instamart
from sites.session import BrowserSession
from llm import extract_products
from display import show_results, show_cart_options, console

ALL_SITES = ["blinkit", "zepto", "instamart"]

# Each site: module, display label, browser window position (x, y)
SITE_CONFIG = {
    "blinkit":   {"mod": blinkit,   "label": "Blinkit",   "x": 700, "y":  0},
    "zepto":     {"mod": zepto,     "label": "Zepto",     "x": 730, "y": 25},
    "instamart": {"mod": instamart, "label": "Instamart", "x": 760, "y": 50},
}


async def run(query: str, sites: list[str]):
    labels = [SITE_CONFIG[s]["label"] for s in sites]
    console.print(f"\n[bold cyan]Searching '{query}' on {', '.join(labels)}…[/bold cyan]")
    console.print("[dim]Browser windows will open on the right — keep this terminal visible.[/dim]\n")

    # ── 1. Open all browsers (one persistent Chromium profile per site) ───────
    sessions: dict[str, BrowserSession] = {}
    for s in sites:
        cfg     = SITE_CONFIG[s]
        session = BrowserSession(s, cfg["x"], cfg["y"])
        await session.start()
        sessions[s] = session

    # ── 2. Search all sites in parallel (pages stay open) ────────────────────
    async def _search(s: str) -> str:
        try:
            return await SITE_CONFIG[s]["mod"].search(sessions[s].page, query)
        except Exception as e:
            return f"ERROR: {e}"

    texts = await asyncio.gather(*[_search(s) for s in sites])

    # ── 3. LLM price extraction ───────────────────────────────────────────────
    console.print("[dim]Extracting prices…[/dim]\n")
    results: dict[str, list[dict]] = {}
    for s, text in zip(sites, texts):
        label = SITE_CONFIG[s]["label"]
        if text.startswith("ERROR"):
            console.print(f"[red]{label}:[/red] {text[7:]}")
            results[label] = []
        else:
            results[label] = extract_products(text, query, label)

    # ── 4. Show comparison table ──────────────────────────────────────────────
    show_results(
        results.get("Blinkit",   []),
        results.get("Zepto",     []),
        query,
        instamart=results.get("Instamart", []),
    )

    # ── 5. Cart selection ─────────────────────────────────────────────────────
    options = show_cart_options(results)
    if not options:
        console.print("[dim]No items available to add.[/dim]")
        await _close_all(sessions)
        return

    try:
        choice = input("Enter key to add to cart (or Enter to skip): ").strip().lower()
    except EOFError:
        await _close_all(sessions)
        return

    matched = next((o for o in options if o["key"] == choice), None)
    if not matched:
        await _close_all(sessions)
        return

    # ── 6. Warn if a cheaper option exists on another site ───────────────────
    chosen_price = matched["product"]["price"]
    chosen_site  = matched["site"]
    cheaper_alts = [
        o for o in options
        if o["site"] != chosen_site
        and o["product"]["price"] < chosen_price
        and o["product"]["name"][:10].lower() == matched["product"]["name"][:10].lower()
    ]
    if cheaper_alts:
        best_alt = min(cheaper_alts, key=lambda o: o["product"]["price"])
        console.print(
            f"\n[yellow]💡 {best_alt['site']} has it cheaper: "
            f"₹{best_alt['product']['price']} ({best_alt['key']})[/yellow]"
        )
        try:
            confirm = input("Continue with your choice? [y/n]: ").strip().lower()
        except EOFError:
            confirm = "y"
        if confirm != "y":
            await _close_all(sessions)
            return

    # ── 7. Close losing site windows ─────────────────────────────────────────
    chosen_site_key = matched["site"].lower()
    for s, session in sessions.items():
        if s != chosen_site_key:
            await session.close()

    # ── 8. Add to cart on the ALREADY OPEN search-results page ───────────────
    product = matched["product"]
    index   = matched["index"]
    console.print(
        f"\n[bold]Adding [cyan]{product['name']}[/cyan] "
        f"to {matched['site']} cart…[/bold]"
    )

    page = sessions[chosen_site_key].page
    mod  = SITE_CONFIG[chosen_site_key]["mod"]
    ok   = await mod.add_to_cart(page, product["name"], index)

    if ok:
        console.print(f"\n[bold green]✓ Added to cart![/bold green]  "
                      f"Complete your order in the browser.")
    else:
        console.print("\n[yellow]⚠ Couldn't auto-click ADD — "
                      "please add it manually in the browser.[/yellow]")

    # ── 9. Keep browser open so user can pay ─────────────────────────────────
    try:
        input("\nPress Enter when you're done with your order… ")
    except EOFError:
        pass

    await sessions[chosen_site_key].close()


async def _close_all(sessions: dict[str, BrowserSession]):
    for session in sessions.values():
        await session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Compare grocery prices on Blinkit, Zepto, Instamart"
    )
    parser.add_argument("query", nargs="*", help="What to search for")
    parser.add_argument(
        "--sites", nargs="+", choices=ALL_SITES, default=ALL_SITES,
        metavar="SITE",
        help=f"Sites to search. Options: {', '.join(ALL_SITES)}",
    )
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query:
        query = input("What are you looking for? ").strip()
    if not query:
        print("No query — exiting.")
        return

    asyncio.run(run(query, args.sites))


if __name__ == "__main__":
    main()
