# Blinkit

## Home Page
- URL: https://blinkit.com (no /s/ in path)
- Search area at top shows rotating suggestions like: Search "bread", Search "sugar", etc.
- This is NOT a regular input — it's a clickable div. Click any "Search ..." text to open the search overlay.
- Once the overlay opens, an actual input field appears — type the query there and press Enter.
- Delivery time promise shown near top left (e.g. "21 minutes")
- Categories listed below the search bar
- If not logged in: shows "Login" link in top right
- If no location set: shows "Set your location" prompt

## Search Results
- URL pattern: blinkit.com/s/?q=...
- Products displayed in a scrollable grid
- Each product card shows (top to bottom):
  - Product image
  - Delivery time (e.g. "10 mins")
  - Product name
  - Weight/unit (e.g. "1 kg", "500 g", "1 L")
  - Price: ₹selling_price, sometimes with ₹MRP crossed out and discount %
  - Green "ADD" button at the bottom of each card
- DOM text order per card: delivery_time, product_name, unit, ₹price, ₹mrp, discount%, ADD
- Products are numbered top-left to bottom-right (1st product = top-left)

## After ADD Click
- The "ADD" button changes to a quantity selector: "−  1  +"
- A green bar/toast may briefly appear at bottom with "View Cart" — but it disappears fast
- BEST approach: use goto https://blinkit.com/checkout to navigate to cart directly
- The cart page shows all items, quantities, and total price

## Text Patterns
- Product extraction from inner_text: look for blocks containing ₹ followed by ADD
- Delivery time usually appears once near top ("in 10 minutes") — applies to all products
- "Notify Me" instead of "ADD" means out of stock
