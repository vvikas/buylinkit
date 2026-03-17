from rich.console import Console
from rich.table import Table
from typing import Optional
from rich.text import Text

console = Console()


def _delivery_str(mins: Optional[int]) -> str:
    if mins is None:
        return ""
    return f"{mins} min"


def _avail_cell(price: Optional[int], available: bool, delivery_mins: Optional[int]) -> Text:
    if not available or price is None:
        return Text("✗ out of stock", style="red dim")
    t = Text(f"₹{price}", style="bold green")
    if delivery_mins:
        t.append(f"  {delivery_mins}m", style="cyan")
    return t


def show_results(blinkit: list[dict], zepto: list[dict], query: str, instamart: Optional[list[dict]] = None):
    instamart = instamart or []
    console.print(f"\n[bold]Results for:[/bold] [cyan]{query}[/cyan]\n")

    if not blinkit and not zepto and not instamart:
        console.print("[red]No results found on any site.[/red]")
        return

    # --- availability summary ---
    b_avail = [p for p in blinkit   if p.get("available", True)]
    z_avail = [p for p in zepto     if p.get("available", True)]
    i_avail = [p for p in instamart if p.get("available", True)]
    avail_sites = (["Blinkit"] if b_avail else []) + (["Zepto"] if z_avail else []) + (["Instamart"] if i_avail else [])
    if avail_sites:
        console.print(f"[bold]✓ Available on:[/bold] {', '.join(avail_sites)}\n")
    else:
        console.print("[bold red]✗ Out of stock everywhere[/bold red]\n")

    # --- price table ---
    show_instamart = bool(instamart)
    table = Table(show_header=True, header_style="bold white", box=None, padding=(0, 2))
    table.add_column("Product", style="white", min_width=25)
    table.add_column("Unit", style="dim", min_width=7)
    table.add_column("Blinkit",   justify="left", min_width=13)
    table.add_column("Zepto",     justify="left", min_width=13)
    if show_instamart:
        table.add_column("Instamart", justify="left", min_width=13)
    table.add_column("Best", min_width=12)

    # pair products across sites by name similarity
    def _match(name: str, pool: list[dict], used: set) -> Optional[dict]:
        for i, p in enumerate(pool):
            if i in used:
                continue
            if name[:12].lower() in p["name"].lower() or p["name"][:12].lower() in name.lower():
                used.add(i)
                return p
        return None

    rows: list[dict] = []
    z_used: set[int] = set()
    i_used: set[int] = set()

    for bp in blinkit:
        mz = _match(bp["name"], zepto,     z_used)
        mi = _match(bp["name"], instamart, i_used)
        rows.append({
            "name": bp["name"], "unit": bp.get("unit", ""),
            "b": bp   if bp.get("available", True) else None,
            "z": mz   if mz and mz.get("available", True) else None,
            "i": mi   if mi and mi.get("available", True) else None,
        })
    for j, zp in enumerate(zepto):
        if j not in z_used:
            mi = _match(zp["name"], instamart, i_used)
            rows.append({
                "name": zp["name"], "unit": zp.get("unit", ""),
                "b": None,
                "z": zp if zp.get("available", True) else None,
                "i": mi if mi and mi.get("available", True) else None,
            })
    for k, ip in enumerate(instamart):
        if k not in i_used:
            rows.append({
                "name": ip["name"], "unit": ip.get("unit", ""),
                "b": None, "z": None,
                "i": ip if ip.get("available", True) else None,
            })

    for r in rows[:8]:
        prices = {s: r[s]["price"] for s in ("b", "z", "i") if r[s]}
        site_labels = {"b": "Blinkit", "z": "Zepto", "i": "Instamart"}
        site_colors = {"b": "green",   "z": "yellow", "i": "magenta"}
        best_key = min(prices, key=prices.get) if prices else None
        badge = Text(f"← {site_labels[best_key]}", style=site_colors[best_key]) if best_key else Text("unavailable", style="dim red")

        row_cells = [
            r["name"][:32],
            r["unit"],
            _avail_cell(r["b"]["price"] if r["b"] else None, bool(r["b"]), r["b"].get("delivery_mins") if r["b"] else None),
            _avail_cell(r["z"]["price"] if r["z"] else None, bool(r["z"]), r["z"].get("delivery_mins") if r["z"] else None),
        ]
        if show_instamart:
            row_cells.append(_avail_cell(r["i"]["price"] if r["i"] else None, bool(r["i"]), r["i"].get("delivery_mins") if r["i"] else None))
        row_cells.append(badge)
        table.add_row(*row_cells)

    console.print(table)

    # --- cheapest available summary ---
    console.print()
    for label, avail, color in [("Blinkit", b_avail, "green"), ("Zepto", z_avail, "yellow"), ("Instamart", i_avail, "magenta")]:
        cheapest = min(avail, key=lambda x: x["price"], default=None)
        if cheapest:
            mins = f"  ({cheapest['delivery_mins']} min delivery)" if cheapest.get("delivery_mins") else ""
            console.print(f"  {label:<12} [{color}]{cheapest['name']}[/{color}]  ₹{cheapest['price']}{mins}")
    console.print()


def show_cart_options(results: dict[str, list[dict]]) -> list[dict]:
    """Print numbered add-to-cart options and return the option list."""
    # results = {"Blinkit": [...], "Zepto": [...], "Instamart": [...]}
    site_colors = {"Blinkit": "green", "Zepto": "yellow", "Instamart": "magenta"}
    site_keys   = {"Blinkit": "b", "Zepto": "z", "Instamart": "i"}

    options = []
    for site, products in results.items():
        for i, p in enumerate(products):
            if p.get("available", True) and p.get("price"):
                options.append({
                    "key":     f"{site_keys[site]}{i+1}",
                    "site":    site,
                    "product": p,
                    "index":   i,   # 0-based position in site's result list
                })

    if not options:
        return options

    console.print("[bold]Add to cart:[/bold]")
    for opt in options:
        p = opt["product"]
        color = site_colors.get(opt["site"], "white")
        mins = f"  [cyan]{p['delivery_mins']}m[/cyan]" if p.get("delivery_mins") else ""
        console.print(
            f"  [{color}]{opt['key']:>3}[/{color}]  "
            f"{p['name'][:35]:<35}  {p.get('unit',''):<10}  "
            f"₹{p['price']:<6}{mins}  [{color}]{opt['site']}[/{color}]"
        )
    console.print()
    return options
