"""
login.py — open each site's persistent browser profile, auto-fill phone
number from .env (PHONE_NUMBER), and wait for you to complete OTP entry.
Run once; login session is saved in the profile and remembered forever.

Usage:
    ./login.sh              # all three sites
    ./login.sh blinkit      # one site only
"""
import asyncio
import os
import sys

from dotenv import load_dotenv
from sites.session import BrowserSession, auto_fill_phone

load_dotenv()

SITES = {
    "blinkit":   ("https://blinkit.com",              660, 30),
    "zepto":     ("https://www.zepto.com",             660, 30),
    "instamart": ("https://www.swiggy.com/instamart",  660, 30),
}


async def setup_site(key: str, url: str, x: int, y: int):
    label = key.capitalize()
    print(f"\n{'─'*52}")
    print(f"  {label}")
    print(f"{'─'*52}")

    session = BrowserSession(key, x, y, width=600, height=720)
    page = await session.start()
    await page.goto(url, timeout=20000)
    await page.wait_for_load_state("domcontentloaded", timeout=15000)
    await page.wait_for_timeout(2000)

    phone = os.getenv("PHONE_NUMBER", "").strip()
    if phone:
        print(f"  Trying to auto-fill phone number…")
        filled = await auto_fill_phone(page)
        if filled:
            masked = phone[:2] + "****" + phone[-2:] if len(phone) >= 4 else phone
            print(f"  ✓ Phone filled ({masked}) — enter the OTP in the browser.")
        else:
            print(f"  Couldn't auto-fill — log in manually in the browser.")
    else:
        print(f"  No PHONE_NUMBER in .env — log in manually in the browser.")
        print(f"  Tip: add PHONE_NUMBER=10digitnumber to .env for auto-fill.")

    try:
        input(f"  ↩  Press Enter once you're logged in and location is set… ")
    except EOFError:
        pass

    await session.close()
    print(f"  ✓ {label} profile saved.")


async def main():
    load_dotenv()
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(SITES.keys())
    invalid = [t for t in targets if t not in SITES]
    if invalid:
        print(f"Unknown sites: {invalid}. Choose from: {list(SITES.keys())}")
        return

    print("BuyLinkit login setup")
    print("Phone number will be auto-filled from .env if PHONE_NUMBER is set.")
    print("You only need to enter the OTP + set your delivery location.\n")

    for key in targets:
        url, x, y = SITES[key]
        await setup_site(key, url, x, y)

    print("\n✓ All done — run ./run.sh 'your query' to start searching.")


if __name__ == "__main__":
    asyncio.run(main())
