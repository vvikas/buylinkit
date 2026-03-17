import asyncio
import argparse

from sites import blinkit, zepto, instamart
from sites.session import BrowserSession, needs_login, needs_location
from llm import extract_products
from display import show_results, show_cart_options, console

ALL_SITES = ["blinkit", "zepto", "instamart"]

# Windows sit on the right half of a 1280×832 logical screen (Retina 2560×1664).
# 660 + 600 = 1260 < 1280  ✓   30 + 720 = 750 < 832  ✓
SITE_CONFIG = {
    "blinkit":   {"mod": blinkit,   "label": "Blinkit",   "x": 660, "y": 30},
    "zepto":     {"mod": zepto,     "label": "Zepto",     "x": 670, "y": 35},
    "instamart": {"mod": instamart, "label": "Instamart", "x": 680, "y": 40},
}
BROWSER_W, BROWSER_H = 600, 720


async def run(query: str, sites: list[str]):
    labels = [SITE_CONFIG[s]["label"] for s in sites]
    console.print(f"\n[bold cyan]Searching '{query}' on {', '.join(labels)}…[/bold cyan]")
    console.print("[dim]Browsers open on the right — keep this terminal visible.[/dim]\n")

    # ── 1. Open all browsers ──────────────────────────────────────────────────
    sessions: dict[str, BrowserSession] = {}
    for s in sites:
        cfg = SITE_CONFIG[s]
        session = BrowserSession(s, cfg["x"], cfg["y"], BROWSER_W, BROWSER_H)
        await session.start()
        sessions[s] = session

    # ── 2. Search all sites in parallel (fast path when already logged in) ───
    async def _search_raw(s: str) -> str:
        """Navigate to search URL and return raw page text — no prompting."""
        mod = SITE_CONFIG[s]["mod"]
        try:
            return await mod.search_raw(sessions[s].page, query)
        except Exception as e:
            return f"ERROR: {e}"

    raw_texts: list[str] = list(
        await asyncio.gather(*[_search_raw(s) for s in sites])
    )
    texts: dict[str, str] = dict(zip(sites, raw_texts))

    # ── 3. Fix login / location issues sequentially (stdin is single-threaded)
    for s in sites:
        label = SITE_CONFIG[s]["label"]
        text  = texts[s]
        page  = sessions[s].page
        mod   = SITE_CONFIG[s]["mod"]

        if text.startswith("ERROR"):
            continue

        # Login wall?
        if needs_login(text, label):
            console.print(f"\n[bold red]🔐 {label}:[/bold red] Not logged in.")
            console.print(f"   Log in inside the [bold]{label}[/bold] browser window, then press Enter.")
            try:
                input("   ↩  Press Enter when done… ")
            except EOFError:
                pass
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=20000)
                await page.wait_for_timeout(3000)
                # Re-run the search now that we're logged in
                texts[s] = await mod.search_raw(page, query)
                text = texts[s]
            except Exception:
                pass

        # Location not set?
        if needs_location(text, label):
            console.print(f"\n[bold yellow]📍 {label}:[/bold yellow] Delivery location not set.")
            console.print(f"   Set it in the [bold]{label}[/bold] browser window, then press Enter.")
            try:
                input("   ↩  Press Enter when done… ")
            except EOFError:
                pass
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                await page.wait_for_timeout(2000)
                texts[s] = await page.inner_text("body")
            except Exception:
                pass

    # ── 4. LLM price extraction ───────────────────────────────────────────────
    console.print("\n[dim]Extracting prices…[/dim]\n")
    results: dict[str, list[dict]] = {}
    for s in sites:
        label = SITE_CONFIG[s]["label"]
        text  = texts[s]
        if text.startswith("ERROR"):
            console.print(f"[red]{label}:[/red] {text[7:]}")
            results[label] = []
        else:
            results[label] = extract_products(text, query, label)

    # ── 5. Show comparison table ──────────────────────────────────────────────
    show_results(
        results.get("Blinkit",   []),
        results.get("Zepto",     []),
        query,
        instamart=results.get("Instamart", []),
    )

    # ── 6. Cart selection ─────────────────────────────────────────────────────
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

    # ── 7. Warn if cheaper elsewhere ─────────────────────────────────────────
    chosen_price    = matched["product"]["price"]
    chosen_site     = matched["site"]
    cheaper_alts    = [
        o for o in options
        if o["site"] != chosen_site
        and o["product"]["price"] < chosen_price
        and o["product"]["name"][:10].lower() == matched["product"]["name"][:10].lower()
    ]
    if cheaper_alts:
        best = min(cheaper_alts, key=lambda o: o["product"]["price"])
        console.print(
            f"\n[yellow]💡 {best['site']} has it cheaper: "
            f"₹{best['product']['price']} ({best['key']})[/yellow]"
        )
        try:
            confirm = input("Continue with your choice? [y/n]: ").strip().lower()
        except EOFError:
            confirm = "y"
        if confirm != "y":
            await _close_all(sessions)
            return

    # ── 8. Close losing site windows ─────────────────────────────────────────
    chosen_key = matched["site"].lower()
    for s, session in sessions.items():
        if s != chosen_key:
            await session.close()

    # ── 9. Add to cart on the already-open search-results page ───────────────
    product = matched["product"]
    index   = matched["index"]
    console.print(
        f"\n[bold]Adding [cyan]{product['name']}[/cyan] to {matched['site']}…[/bold]"
    )

    ok = await SITE_CONFIG[chosen_key]["mod"].add_to_cart(
        sessions[chosen_key].page, product["name"], index
    )

    if ok:
        console.print("\n[bold green]✓ Added to cart![/bold green]  Complete your order in the browser.")
    else:
        console.print("\n[yellow]⚠ Couldn't auto-click ADD — add it manually in the browser.[/yellow]")

    # ── 10. Keep browser open for payment ────────────────────────────────────
    try:
        input("\nPress Enter when you're done with your order… ")
    except EOFError:
        pass
    await sessions[chosen_key].close()


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
