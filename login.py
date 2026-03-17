"""
login.py — open each site's persistent browser profile so you can log in
and set your delivery location. Run this once; credentials are remembered.

Usage:
    ./login.sh              # all three sites
    ./login.sh blinkit      # one site only
"""
import asyncio
import sys
from sites.session import BrowserSession, PROFILE_DIR

SITES = {
    "blinkit":   ("https://blinkit.com",                   660, 30),
    "zepto":     ("https://www.zepto.com",                 660, 30),
    "instamart": ("https://www.swiggy.com/instamart",      660, 30),
}


async def setup_site(key: str, url: str, x: int, y: int):
    print(f"\n{'─'*50}")
    print(f"  Opening {key.capitalize()} — log in and set your delivery location.")
    print(f"  Close the browser or press Enter here when done.")
    print(f"{'─'*50}")
    session = BrowserSession(key, x, y, width=600, height=720)
    page = await session.start()
    await page.goto(url, timeout=20000)
    try:
        input(f"  Press Enter when done with {key.capitalize()}… ")
    except EOFError:
        pass
    await session.close()
    print(f"  ✓ {key.capitalize()} profile saved.")


async def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(SITES.keys())
    invalid = [t for t in targets if t not in SITES]
    if invalid:
        print(f"Unknown sites: {invalid}. Choose from: {list(SITES.keys())}")
        return
    print("BuyLinkit login setup")
    print("Each site will open in its own browser window.")
    print("Log in + set your delivery location, then press Enter to continue.\n")
    for key in targets:
        url, x, y = SITES[key]
        await setup_site(key, url, x, y)
    print("\n✓ All done — run ./run.sh 'your query' to start searching.")


if __name__ == "__main__":
    asyncio.run(main())
