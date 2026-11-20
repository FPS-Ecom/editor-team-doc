---
name: invoice
description: Turn a supplier (China) LED neon sign quote image or PDF into a finished FUSE NEON customer quote PDF in CAD, with the markup from config.json applied. Use when the user uploads a supplier quote and asks for a quote or invoice, or types /invoice. Also use when the user asks to change the markup, margin, or exchange rate.
---

# FUSE NEON quote builder

Input: a supplier quote (image or PDF) showing a sign mockup, its size, specs, and USD prices.
Output: a one-page FUSE NEON "Custom Product Quote" PDF in CAD. The supplier's prices never appear on it.

All math lives in `build_quote.py` and `config.json`. You read the supplier quote and write a small JSON file; the script does the rest.

## Changing the markup, margin, or exchange rate

Edit `config.json` in this folder. The fields that matter:

- `usd_to_cad` - exchange rate applied to every supplier line.
- `pricing_mode` - `markup` (percent added on top of cost) or `margin` (percent of the final sale price).
- `percent.product` - applied to neon price, UV print, acrylic, and any other product line.
- `percent.shipping` - applied to shipping and freight lines.
- `round_total_to` - `1` for whole dollars, `5` for nearest five, `0.01` for cents.

When the user says something like "set the markup to 80 percent", edit the number, show them the new config lines, and offer to rebuild the last quote.

## Building a quote

1. **Find the file.** Uploads land in `/root/.claude/uploads/<session>/`. If the user gave a path, use that.

2. **Read the supplier quote** with the Read tool (PDF or image). Pull out:
   - product name (the business name on the sign if there is one, otherwise "Custom LED Sign")
   - size in cm (W x H)
   - specs worth showing the customer: backing material and colour, lighting colour, mounting kit, remote or app, quantity. Do not list prices or anything in USD.
   - every price line in USD, and the supplier total.
   - Classify each price line: `product` for neon price, uv print, acrylic, extras; `shipping` for shipping, freight, DHL, courier.

3. **Decide the crop.** The supplier image usually has the artwork on top and a text block with USD prices below or beside it. Choose a crop box, as fractions of width and height, that keeps the artwork and the dimension label but removes every USD price. If the prices cannot be separated by a rectangle, crop to the artwork only.

4. **Write the extraction JSON** to the scratchpad directory:

```json
{
  "product_name": "Puppy Love Spa & Salon",
  "prepared_for": "customer@example.com",
  "subtitle": "",
  "sign_type": "Custom LED neon sign",
  "size_cm": {"w": 114, "h": 62.6},
  "specs": [["Backing", "Black acrylic"], ["Lighting", "Hot pink LED"], ["Quantity", "1 sign"]],
  "lines": [
    {"label": "neon price", "usd": 286, "type": "product"},
    {"label": "uv print", "usd": 25, "type": "product"},
    {"label": "shipping cost", "usd": 208, "type": "shipping"}
  ],
  "supplier_total_usd": 519,
  "crop": {"left": 0, "top": 0, "right": 1, "bottom": 0.58},
  "image_caption": "Supplied artwork and LED layout"
}
```

   Field notes:
   - `prepared_for` is optional. If the user names the customer or gives an email, put it here. It becomes "Prepared for ..." under the title.
   - `subtitle` overrides the "Prepared for" line. Use it for a material note such as "LED + (with app)" when there is no customer.
   - `title` is optional and defaults to `product_name`.
   - `date` is optional and defaults to today, formatted like "November 19, 2026".
   - `specs` are shown after the automatic Product, Size, and Imperial rows. Three to four rows looks best.
   - `image_caption` is "Supplied artwork and LED layout" when the mockup is the customer's artwork, or "Product proof and construction reference" when it is a construction drawing.

5. **Run the build.** `build_quote.py` lives in this skill's folder (the directory that holds this SKILL.md); use its full path:

```bash
python3 -I /path/to/skills/invoice/build_quote.py \
  --input "/path/to/supplier-quote.jpg" \
  --extract "/path/to/extract.json" \
  --out "/path/to/FUSE Quote - Puppy Love Spa & Salon.pdf"
```

   It prints a pricing breakdown and writes the PDF plus a `.png` preview next to it. If it warns that the lines do not add up to the supplier total, re-read the supplier quote and fix the lines before going on.

5b. **Optional: add a picture of the lit sign on a wall.** The quote can carry a second image: a render of the finished sign glowing on a white wall becomes the main picture, and the supplier drawing shrinks to a small construction-reference strip underneath. Two ways to get it, in order of quality:

   - **AI render (the house style).** `assets/render-style-reference.jpg` shows the look the customer expects: a photoreal product shot, the sign mounted on a smooth warm taupe plaster wall, soft even studio light, straight-on view, a glow halo on the wall, small metal standoff screws. Steps:
     1. Crop the supplier image to the artwork only (no prices, no dimension text) and save it as a PNG.
     2. Upload that PNG and `assets/render-style-reference.jpg` to Higgsfield: `media_upload` for each, PUT the bytes with curl, then `media_confirm`.
     3. Call `generate_image` with model `gpt_image_2_6`, aspect ratio `4:3`, quality `medium`, resolution `1k`, `use_unlim: false`, both uploads under role `image_references` (artwork first, style second), and a prompt built from this one, adapting the middle sentence to the sign in hand:

        > Photorealistic product mockup in the exact style of the second reference image: a custom sign mounted on a smooth warm taupe plaster wall, soft even studio lighting, straight-on view, subtle shadow, glowing halo of light cast on the wall around the sign. The sign itself is the one drawn in the first reference image: [describe the shape, backing, LED colours and any lettering exactly as drawn]. Reproduce the layout, proportions and colours exactly as drawn. [Backing material] backing, small round metal standoff screws, no visible cable. Fill the frame with the sign. No text other than the sign's own lettering, no labels, no captions, no watermark, no people, no extra objects.

     4. Poll with `jobs_wait` until the job completes, download `result_url` with curl, and pass the file as `--render`.
     5. Look at the render before using it. If the shape, colours or lettering drift from the drawing, generate once more with a more specific description; do not ship a render that misrepresents the sign.

     Each render spends about 0.25 Higgsfield credits, so generate only when the user wants a render on the quote. The session's environment must allow `upload.higgsfield.ai` and the results host `d8j0ntlcm91z4.cloudfront.net`; the "editor-team-doc" cloud environment already does.
   - **Code-only glow (free fallback).** `python3 -I led_preview.py --input artwork.png --out preview.png` adds a glow to the LED strokes and puts the sign on a plain wall. It looks like a diagram with glow, not a photo. Use it when the user wants a preview but not the credit spend, or when the AI route is unavailable.

   Then add `--render preview.png` to the build command. `render_caption` in the extraction JSON overrides the default caption "Preview of the finished sign, lit".

6. **Check the preview** with the Read tool. Confirm: no USD price is visible in the image, the size and specs match the supplier quote, and the total matches the breakdown. If a price is still visible, tighten the crop and rebuild.

7. **Deliver.** Send the PDF to the user with SendUserFile, and give them the breakdown in chat: supplier total in USD, rate, percent used, and the CAD total. Never put supplier costs in the PDF itself.

## Requirements

- Python 3 with Pillow
- Node with Playwright and its Chromium (`npm install playwright && npx playwright install chromium` on a machine that lacks it)
- poppler-utils (`pdfimages`, `pdftoppm`) for PDF input and the preview

Claude Code cloud sessions have all three. The page size is 12 x 8 inches, matching the original quotes.

## Files

- `config.json` - pricing settings and the fixed wording on the quote
- `build_quote.py` - crops the image, applies pricing, fills the template, renders the PDF
- `led_preview.py` - free code-only glow preview of the sign on a wall, for the optional render panel
- `assets/render-style-reference.jpg` - the look the AI render should match
- `template.html` - the quote layout
- `render.js` - HTML to PDF via Playwright
- `assets/fuse-neon-logo.png` - logo shown top right
