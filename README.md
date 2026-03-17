# 🛒 BuyLinkit

> *Blinkit + Zepto + Instamart — price compare and add to cart, all from your terminal.*

BuyLinkit searches multiple 10-minute delivery services simultaneously, shows you a side-by-side price table, and adds your chosen item to the cart — in the **same browser window** that did the search. No reopening, no guessing.

![BuyLinkit demo](demo.png)

---

## Features

- **Parallel search** across Blinkit, Zepto, and Swiggy Instamart
- **Price comparison table** with delivery time and best-price highlight
- **Smart cart** — clicks ADD by position index on the already-open page, so the right item always gets added
- **Cheaper-elsewhere warning** — alerts you if another site has it for less before you confirm
- **Persistent browser profiles** — set your location and log in once, remembered forever
- **No payment automation** — you pay yourself; the bot just gets you to checkout

---

## Requirements

- macOS (uses persistent Chromium profiles)
- Python 3.10+
- A free [Groq API key](https://console.groq.com) — used for price extraction (Llama 3.3 70B)

---

## Setup

```bash
git clone https://github.com/vvikas/buylinkit.git
cd buylinkit
./setup.sh
```

Then copy `.env.example` to `.env` and add your Groq key:

```bash
cp .env.example .env
# edit .env and set GROQ_API_KEY=your_key_here
```

---

## First-time login (once per machine)

Before searching, log in to each site and set your delivery location. The persistent browser profile saves everything permanently.

```bash
./login.sh                  # all 3 sites
./login.sh blinkit          # one site only
./login.sh blinkit zepto    # two sites
```

This opens each site's browser one at a time. Log in manually (phone + OTP), set your delivery address, then press Enter in the terminal. Done — you won't need to do this again.

If a site stops recognizing your session later:
```bash
./login.sh blinkit          # re-login to that site only
```

---

## Usage

```bash
./run.sh 'chocolate icecream'
./run.sh 'onions 1kg'
./run.sh 'amul butter'

# Search specific sites only
./run.sh 'milk' --sites blinkit zepto
```

### Workflow

```
Terminal                          Browser (right side of screen)
────────────────────────────────  ──────────────────────────────
$ ./run.sh 'chocolate icecream'
Searching on Blinkit, Zepto…      [3 windows open on right]
Extracting prices…

Results for: chocolate icecream
  #   Product          Blinkit  Zepto  Instamart
  b1  NIC Choco Chips  ₹322     —      —
  b2  Amul Brownie     ₹210     —      —
  z1  Kwality Walls    ₹35      ₹34    —        ← Zepto cheapest

Add to cart (or Enter to skip): z1
                                  [Blinkit+Instamart windows close]
💡 Blinkit has it cheaper: ₹35 (b2) — Continue? [y/n]: y
                                  [ADD clicked on Zepto]
                                  [cart page opens]
✓ Added to cart! Complete your
  order in the browser.
Press Enter when done…
```

---

## Project structure

```
buylinkit/
  main.py           # CLI entry — orchestrates the full flow
  llm.py            # Groq client — price extraction + LLM cart navigation
  display.py        # Rich terminal table
  sites/
    session.py      # BrowserSession, do_search, click_add_button
    blinkit.py      # Blinkit scraper + cart
    zepto.py        # Zepto scraper + cart
    instamart.py    # Swiggy Instamart scraper + cart
  setup.sh          # One-time install (venv + playwright)
  login.sh          # Login helper (wraps: main.py --login)
  run.sh            # Search wrapper (wraps: main.py)
  requirements.txt
```

---

## How it works

1. **Opens one persistent Chromium window per site** (positions them to the right so the terminal stays visible)
2. **Searches all sites in parallel** — navigates to the search URL, waits for JS to render, grabs body text
3. **Sends page text to Groq** (Llama 3.3 70B) — extracts structured `{name, price, unit, available}` per product
4. **Renders a Rich comparison table** in the terminal
5. **On selection**: closes losing-site windows, clicks the Nth ADD button (by list position) on the still-open search-results page, navigates to cart
6. **Browser stays open** for you to review the cart and pay

---

## Adding more sites

Each site is a small module in `sites/` with two async functions:

```python
async def search(page: Page, query: str) -> str:
    # navigate + return page body text

async def add_to_cart(page: Page, product_name: str, product_index: int) -> bool:
    # click ADD and navigate to cart
```

Add the module to `SITE_CONFIG` in `main.py` with a window position and you're done.

---

## License

MIT
