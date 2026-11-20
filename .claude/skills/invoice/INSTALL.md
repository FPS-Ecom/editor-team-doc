# FUSE NEON quote skill - install

This folder is a Claude Code skill. Once it is in place, you upload a supplier
(China) sign quote in a Claude Code session, type `/invoice`, and get back a
finished FUSE NEON quote PDF in CAD with the standard markup applied.

## 1. Put the folder where Claude Code looks for skills

Pick one:

- **For every project on your machine:** copy this folder to `~/.claude/skills/invoice/`
- **For one project only:** copy it to `<project>/.claude/skills/invoice/` inside that project

The folder name should stay `invoice`. Restart Claude Code (or start a new session)
and `/invoice` will show up.

## 2. Install the three tools the build needs

- Python 3 with Pillow: `pip install pillow`
- Node with Playwright and its Chromium: `npm install -g playwright && npx playwright install chromium`
- poppler-utils (`pdfimages`, `pdftoppm`): `brew install poppler` on a Mac, `apt install poppler-utils` on Linux

Claude Code cloud sessions already have all three, so nothing to install there.

## 3. Set your pricing once

Open `config.json` and set:

- `usd_to_cad` - the exchange rate you want applied
- `percent.product` and `percent.shipping` - currently 40 (percent markup on cost)

You can also just tell Claude "set the markup to 35 percent" in a session and it
will edit the file for you.

## 4. Optional: the lit-sign render on the quote

The quote can show a photoreal picture of the finished sign on a wall. That uses
the Higgsfield connector in Claude (connect it under Settings > Connectors) and
costs about 0.25 Higgsfield credits per image. In a cloud session the environment
must allow the hosts `upload.higgsfield.ai` and `d8j0ntlcm91z4.cloudfront.net`.
Without it, the quote still works; Claude can use the free `led_preview.py` glow
instead or leave the render panel off.

## Files

- `SKILL.md` - what Claude does when you type `/invoice`
- `config.json` - pricing and the fixed wording on the quote
- `build_quote.py` - pricing math, image crop, PDF build
- `template.html` - the quote layout
- `render.js` - HTML to PDF
- `led_preview.py` - free glow preview of the sign on a wall
- `assets/fuse-neon-logo.png` - your logo
- `assets/render-style-reference.jpg` - the look the AI render should match
