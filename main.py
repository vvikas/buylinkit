import asyncio
import argparse
import os

from sites import blinkit, zepto, instamart
from sites.session import BrowserSession, needs_login, needs_location, _get_screen_size
from llm import extract_products
from display import show_results, show_cart_options, console

ALL_SITES = ["blinkit", "zepto", "instamart"]
DEFAULT_SITES = ["blinkit", "zepto"]

SITE_CONFIG = {
    "blinkit":   {"mod": blinkit,   "label": "Blinkit"},
    "zepto":     {"mod": zepto,     "label": "Zepto"},
    "instamart": {"mod": instamart, "label": "Instamart"},
}


_MENU_BAR_H     = 25   # macOS menu bar
_BROWSER_CHROME = 90   # Chromium title bar + tabs + address bar



def _browser_positions(n: int) -> list:
    """Right half of screen, browsers stacked vertically, accounting for browser chrome."""
    sw, sh = _get_screen_size()
    x        = sw // 2
    w        = sw // 2                          # exact half — avoids right-edge overflow
    usable_h = sh - _MENU_BAR_H                # subtract macOS menu bar
    slot_h   = usable_h // n
    viewport_h = max(slot_h - _BROWSER_CHROME, 400)
    return [
        {
            "position": (x, _MENU_BAR_H + i * slot_h),
            "size": (w, viewport_h),
        }
        for i in range(n)
    ]


async def run(query: str, sites: list[str]):
    labels = [SITE_CONFIG[s]["label"] for s in sites]
    console.print(f"\n[bold cyan]Searching '{query}' on {', '.join(labels)}…[/bold cyan]\n")

    # ── 1. Open all browsers tiled on the right half of the screen ───────────
    sessions: dict[str, BrowserSession] = {}
    positions = _browser_positions(len(sites))
    for i, s in enumerate(sites):
        p = positions[i]
        session = BrowserSession(s, position=p["position"], size=p["size"])
        await session.start()
        sessions[s] = session

    # ── 2. Search all sites in parallel (fast path when already logged in) ───
    async def _search_raw(s: str) -> str:
        mod = SITE_CONFIG[s]["mod"]
        try:
            return await mod.search_raw(sessions[s].page, query)
        except Exception as e:
            return f"ERROR: {e}"

    raw_texts: list[str] = list(
        await asyncio.gather(*[_search_raw(s) for s in sites])
    )
    texts: dict[str, str] = dict(zip(sites, raw_texts))

    # ── 3. Handle location issues (login is handled by --login mode) ──────────
    for s in sites:
        label = SITE_CONFIG[s]["label"]
        text  = texts[s]
        page  = sessions[s].page

        if text.startswith("ERROR"):
            continue

        # Not logged in → tell user to run --login first
        if needs_login(text, label, page.url):
            console.print(
                f"\n[bold red]🔐 {label}:[/bold red] Not logged in. "
                f"Run [bold]./run.sh --login --sites {s}[/bold] first."
            )
            texts[s] = "ERROR: not logged in"
            continue

        # Location not set? Bring browser to front so user can set it
        if needs_location(text, label):
            console.print(f"\n[bold yellow]📍 {label}:[/bold yellow] Delivery location not set.")
            await sessions[s].bring_to_front()
            console.print(f"   Set your delivery location in the {label} browser, then press Enter.")
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

    # ── 8. Close other site browsers ───────────────────────────────────────────
    chosen_key = matched["site"].lower()
    for s, session in sessions.items():
        if s != chosen_key:
            await session.close()

    # ── 9. Add to cart (still minimized) ─────────────────────────────────────
    product = matched["product"]
    index   = matched["index"]
    console.print(
        f"\n[bold]Adding [cyan]{product['name']}[/cyan] to {matched['site']}…[/bold]"
    )

    chosen_session = sessions[chosen_key]
    ok = await SITE_CONFIG[chosen_key]["mod"].add_to_cart(
        chosen_session.page, product["name"], index
    )

    # ── 10. Navigate to cart and bring browser to front for checkout ─────────
    cart_urls = {
        "blinkit":   "https://blinkit.com/checkout",
        "zepto":     "https://www.zepto.com/?cart=open",
        "instamart": "https://www.swiggy.com/instamart/checkout",
    }
    cart_url = cart_urls.get(chosen_key, SITE_CONFIG[chosen_key]["mod"].START_URL)
    await chosen_session.page.goto(cart_url, timeout=20000)
    await chosen_session.page.wait_for_load_state("domcontentloaded", timeout=15000)
    await chosen_session.bring_to_front()

    if ok:
        console.print("\n[bold green]✓ Added to cart![/bold green]  Complete your order in the browser.")
    else:
        console.print("\n[yellow]⚠ Couldn't auto-click ADD — try adding it manually in the browser.[/yellow]")

    try:
        input("\nPress Enter when you're done with your order… ")
    except EOFError:
        pass
    await chosen_session.close()


async def _close_all(sessions: dict[str, BrowserSession]):
    for session in sessions.values():
        await session.close()


# ── Dedicated login mode ───────────────────────────────────────────────────

async def login_mode(sites: list[str]):
    """
    Open each site one at a time. User logs in + sets location manually.
    The persistent browser profile saves the session for future runs.
    """
    for s in sites:
        label = SITE_CONFIG[s]["label"]
        mod   = SITE_CONFIG[s]["mod"]

        console.print(f"\n[bold cyan]──────── {label} ────────[/bold cyan]")
        console.print(f"   Opening {label} — log in and set your delivery location.")

        session = BrowserSession(s)
        await session.start()
        page = session.page

        await page.goto(mod.START_URL, timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=20000)

        try:
            input(f"   ↩  Press Enter once logged in + location set for {label}… ")
        except EOFError:
            pass

        # Verify — browser may have been closed by user, handle gracefully
        try:
            text = await page.inner_text("body")
            url  = page.url
            if needs_login(text, label, url):
                console.print(f"   [yellow]⚠ Still looks like {label} is not logged in.[/yellow]")
            elif needs_location(text, label):
                console.print(f"   [yellow]⚠ Location still not set for {label}.[/yellow]")
            else:
                console.print(f"   [green]✓ {label} ready.[/green]")
        except Exception:
            console.print(f"   [yellow]⚠ Browser was closed — session may not be saved. Run again.[/yellow]")

        await session.close()

    console.print("\n[bold green]✓ Done. Run ./run.sh 'your query' to start shopping.[/bold green]\n")


def main():
    parser = argparse.ArgumentParser(
        description="Compare grocery prices on Blinkit, Zepto, Instamart"
    )
    parser.add_argument("query", nargs="*", help="What to search for")
    parser.add_argument(
        "--sites", nargs="+", choices=ALL_SITES, default=DEFAULT_SITES,
        metavar="SITE",
        help=f"Sites to search/login. Options: {', '.join(ALL_SITES)}",
    )
    parser.add_argument(
        "--login", action="store_true",
        help="Run the login flow for each site (do this once per machine).",
    )
    args = parser.parse_args()

    if args.login:
        asyncio.run(login_mode(args.sites))
        return

    query = " ".join(args.query).strip()
    if not query:
        query = input("What are you looking for? ").strip()
    if not query:
        print("No query — exiting.")
        return

    asyncio.run(run(query, args.sites))


if __name__ == "__main__":
    main()
