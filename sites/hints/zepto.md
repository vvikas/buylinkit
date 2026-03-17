# Zepto

## Home Page
- URL: https://www.zepto.com
- Search area at top shows rotating suggestions like: Search for "kurkure", "apple juice", etc.
- Clicking the search area navigates to /search page where a real input appears.
- The search input has placeholder "Search for over 5000 products".
- Click the input if not focused, type the query, press Enter.
- Categories listed below: All, Cafe, Home, Toys, Fresh, etc.
- If not logged in: "Login" or "Profile" in top right
- If no location set: location prompt appears

## Search Results
- URL pattern: zepto.com/search?query=...
- Products displayed in a scrollable grid
- Each product card shows:
  - "ADD" button
  - ₹selling_price
  - ₹MRP (crossed out)
  - Discount amount (e.g. ₹60 OFF)
  - Product name
  - Weight/unit (e.g. "1 pack (1 kg)")
  - Delivery time (e.g. "14 mins")
- DOM text order per card: ADD, ₹price, ₹mrp, ₹discount OFF, product_name, unit, delivery_time
- Products are numbered left-to-right, top-to-bottom

## After ADD Click
- The "ADD" button changes to a quantity selector: "−  1  +"
- Cart icon in top right updates with item count
- BEST approach: use goto https://www.zepto.com/?cart=open to open cart panel directly
- Cart panel shows: Item Total, To Pay, "Add Address to proceed"
- Zepto has NO /cart or /checkout URL — only /?cart=open works

## Text Patterns
- Product extraction from inner_text: look for blocks with ADD followed by ₹price
- "Notify" or "Out of Stock" means item is unavailable
