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

## Usage

```bash
./run.sh 'chocolate icecream'
./run.sh 'onions 1kg'
./run.sh 'amul butter'

# Search specific sites only
./run.sh 'milk' --sites blinkit zepto
```

**First run per site:** the browser will open and ask you to set your delivery location. Do it once — the profile remembers it.

### Workflow

```
Terminal                          Browser (right side of screen)
────────────────────────────────  ──────────────────────────────
$ ./run.sh 'chocolate icecream'
Searching on Blinkit, Zepto…      [Blinkit opens] [Zepto opens]
Extracting prices…
                                  [windows close after scraping]
Results for: chocolate icecream
  Product          Blinkit  Zepto  Best
  NIC Choco Chips  ₹322     —      ← Blinkit
  Amul Brownie     ₹210     —      ← Blinkit
  Baskin Robbins   ₹80      —      ← Blinkit
  Kwality Walls    ₹35      ₹34    ← Zepto   ✓ cheapest

Add to cart: z1
                                  [Zepto window stays open]
                                  [ADD clicked, cart opens]
✓ Added to cart! Complete your
  order in the browser.
Press Enter when done…
```

---

## Project structure

```
buylinkit/
  main.py           # CLI entry — orchestrates the full flow
  llm.py            # Groq client — extracts products from raw page text
  display.py        # Rich terminal table
  sites/
    session.py      # BrowserSession class + click_add_button
    blinkit.py      # Blinkit scraper + cart
    zepto.py        # Zepto scraper + cart
    instamart.py    # Swiggy Instamart scraper + cart
  setup.sh          # One-time install (venv + playwright)
  run.sh            # Run wrapper
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
