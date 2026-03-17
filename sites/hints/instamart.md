# Instamart (Swiggy)

## Home Page
- URL: https://www.swiggy.com/instamart
- Search bar at top — click to focus, type query, press Enter
- Categories listed below the search area
- If not logged in: "Login" or "Sign in" option in top right
- If no location set: location prompt or "Set Location" appears

## Search Results
- URL changes after search to reflect the query
- Products displayed in a scrollable grid
- Each product card shows:
  - Product image
  - Product name
  - Weight/unit (e.g. "1 kg", "500 g", "1 L")
  - Price: ₹selling_price, sometimes with ₹MRP crossed out and discount %
  - "ADD" button at the bottom of each card
- DOM text order per card: product_name, unit, ₹price, ₹mrp, discount%, ADD
- Products are numbered left-to-right, top-to-bottom

## After ADD Click
- The "ADD" button changes to a quantity selector: "−  1  +"
- A cart bar or icon updates to show item count
- Navigate to cart using the cart icon or checkout bar

## Text Patterns
- Product extraction from inner_text: look for blocks containing ₹ followed by ADD
- "Out of Stock" or "Notify Me" means item is unavailable
