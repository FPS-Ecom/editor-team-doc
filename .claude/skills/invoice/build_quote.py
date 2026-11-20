#!/usr/bin/env python3
"""
Build a FUSE NEON customer quote PDF from a supplier (China) quote image.

Usage:
  python3 build_quote.py --input supplier.jpg --extract extract.json --out "FUSE Quote - Name.pdf"

  --input    the supplier quote: .jpg / .png / .pdf
  --extract  JSON written by Claude after reading the supplier quote (schema in SKILL.md)
  --out      output PDF path (a .png preview is written next to it)
  --config   optional, defaults to config.json beside this script
  --render   optional image of the lit sign on a wall; shown as the main picture, with the
             supplier drawing kept underneath as a small construction reference

Everything numeric (currency conversion, markup, rounding) happens here, not in the model.
"""
import argparse
import base64
import datetime as dt
import html
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- input image

def load_source_image(path, workdir):
    """Return a PIL image of the supplier quote. PDFs: take the largest embedded image, else rasterise page 1."""
    ext = os.path.splitext(path)[1].lower()
    if ext != ".pdf":
        return Image.open(path).convert("RGB")

    prefix = os.path.join(workdir, "emb")
    subprocess.run(["pdfimages", "-png", "-f", "1", "-l", "1", path, prefix], check=False)
    candidates = [os.path.join(workdir, f) for f in os.listdir(workdir) if f.startswith("emb")]
    best = None
    for c in candidates:
        try:
            im = Image.open(c)
        except Exception:
            continue
        if im.width * im.height < 200 * 200:
            continue
        if best is None or im.width * im.height > best.width * best.height:
            best = im
    if best is not None:
        return best.convert("RGB")

    subprocess.run(["pdftoppm", "-r", "200", "-f", "1", "-l", "1", "-png", path, os.path.join(workdir, "page")], check=True)
    pages = sorted(f for f in os.listdir(workdir) if f.startswith("page"))
    if not pages:
        die("could not rasterise the PDF")
    return Image.open(os.path.join(workdir, pages[0])).convert("RGB")


def crop_image(im, crop):
    """crop = {left, top, right, bottom} as fractions of width/height (0..1). Missing = full image."""
    if not crop:
        return im
    l = float(crop.get("left", 0)); t = float(crop.get("top", 0))
    r = float(crop.get("right", 1)); b = float(crop.get("bottom", 1))
    if not (0 <= l < r <= 1 and 0 <= t < b <= 1):
        die(f"bad crop box {crop}")
    box = (round(l * im.width), round(t * im.height), round(r * im.width), round(b * im.height))
    return im.crop(box)


# ---------------------------------------------------------------- pricing

def price_line(usd, pct, mode, fx):
    cad_cost = usd * fx
    if mode == "markup":
        return cad_cost * (1 + pct / 100.0)
    if mode == "margin":
        if pct >= 100:
            die("margin percent must be below 100")
        return cad_cost / (1 - pct / 100.0)
    die(f"unknown pricing_mode {mode!r} (use 'markup' or 'margin')")


def round_to(value, step):
    if step <= 0:
        return value
    return round(value / step) * step


def compute_pricing(extract, cfg):
    fx = float(cfg["usd_to_cad"])
    mode = cfg.get("pricing_mode", "markup")
    pct = cfg["percent"]
    rows = []
    total = 0.0
    supplier_total = 0.0
    for line in extract["lines"]:
        kind = line.get("type", "product")
        if kind not in pct:
            die(f"line type {kind!r} has no percent in config.json")
        usd = float(line["usd"])
        sell = price_line(usd, float(pct[kind]), mode, fx)
        rows.append((line.get("label", kind), kind, usd, usd * fx, float(pct[kind]), sell))
        total += sell
        supplier_total += usd

    declared = extract.get("supplier_total_usd")
    if declared is not None and abs(float(declared) - supplier_total) > 0.5:
        print(f"WARNING: supplier lines sum to {supplier_total:.2f} USD but the quote says {declared} USD. Check the extraction.", file=sys.stderr)

    rounded = round_to(total, float(cfg.get("round_total_to", 1)))
    return rows, supplier_total, total, rounded


def fmt_money(v, currency, step):
    if step >= 1:
        return f"${v:,.0f} {currency}"
    return f"${v:,.2f} {currency}"


# ---------------------------------------------------------------- template

def fmt_dim(cm):
    v = round(float(cm), 2)
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s


def fmt_in(cm):
    v = round(float(cm) / 2.54, 2)
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s


def data_uri(path_or_image, fmt="PNG"):
    if isinstance(path_or_image, str):
        with open(path_or_image, "rb") as f:
            raw = f.read()
        mime = "image/png" if path_or_image.lower().endswith(".png") else "image/jpeg"
    else:
        import io
        buf = io.BytesIO()
        path_or_image.save(buf, format=fmt)
        raw = buf.getvalue()
        mime = "image/png"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def build_html(extract, cfg, image, total_str, render_path=None):
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()

    w = extract["size_cm"]["w"]; h = extract["size_cm"]["h"]
    specs = [("Product", extract["product_name"]),
             ("Size", f"{fmt_dim(w)} W x {fmt_dim(h)} H cm"),
             ("Imperial", f"{fmt_in(w)} W x {fmt_in(h)} H in")]
    for row in extract.get("specs", []):
        specs.append((row[0], row[1]))

    spec_rows = "\n".join(
        f'<tr><td class="k">{html.escape(str(k))}</td><td class="v">{html.escape(str(v))}</td></tr>' for k, v in specs
    )

    prepared_for = (extract.get("prepared_for") or "").strip()
    subtitle = extract.get("subtitle") or (f"Prepared for {prepared_for}" if prepared_for else "")
    date = extract.get("date") or dt.date.today().strftime("%B %d, %Y").replace(" 0", " ")

    values = {
        "pdf_title": f"{cfg['company'].title()} Quote - {extract['product_name']} - {fmt_dim(w)} x {fmt_dim(h)} cm",
        "document_title": cfg["document_title"],
        "title": extract.get("title") or extract["product_name"],
        "subtitle": subtitle,
        "company": cfg["company"],
        "logo_src": data_uri(os.path.join(HERE, "assets", "fuse-neon-logo.png")),
        "date": date,
        "hero_src": data_uri(render_path) if render_path else data_uri(image),
        "hero_caption": (extract.get("render_caption") or "Preview of the finished sign, lit") if render_path
                        else (extract.get("image_caption") or "Supplied artwork and LED layout"),
        "left_class": " with-render" if render_path else "",
        "ref_panel": (
            '<div class="ref"><img src="' + data_uri(image) + '" alt="Reference">'
            '<div><div class="caption">' + html.escape(extract.get("image_caption") or "Supplied artwork and LED layout") + '</div>'
            '<div class="sub">Preview is illustrative. Final colour and brightness confirmed at approval.</div></div></div>'
        ) if render_path else "",
        "footnote_1": cfg["footnote_1"],
        "footnote_2": cfg["footnote_2"],
        "sign_type": extract.get("sign_type") or "Custom LED neon sign",
        "spec_rows": spec_rows,
        "total": total_str,
        "footer_title": cfg["footer_title"],
        "footer_text": cfg["footer_text"],
    }
    out = tpl
    for k, v in values.items():
        raw = k in ("spec_rows", "logo_src", "hero_src", "ref_panel", "left_class")
        out = out.replace("{{" + k + "}}", v if raw else html.escape(str(v)))
    return out


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--extract", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--render", help="optional image of the lit sign on a wall (AI render or led_preview.py output)")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    with open(args.extract, encoding="utf-8") as f:
        extract = json.load(f)
    for key in ("product_name", "size_cm", "lines"):
        if key not in extract:
            die(f"extract.json is missing '{key}'")

    rows, supplier_total, raw_total, total = compute_pricing(extract, cfg)
    currency = cfg["currency"]
    step = float(cfg.get("round_total_to", 1))
    total_str = fmt_money(total, currency, step)

    workdir = tempfile.mkdtemp(prefix="fuse-quote-")
    try:
        im = load_source_image(args.input, workdir)
        im = crop_image(im, extract.get("crop"))
        render_path = args.render or extract.get("render_image")
        if render_path and not os.path.exists(render_path):
            die(f"render image not found: {render_path}")
        html_text = build_html(extract, cfg, im, total_str, render_path)
        html_path = os.path.join(workdir, "quote.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_text)

        out_pdf = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out_pdf) or ".", exist_ok=True)
        subprocess.run(["node", os.path.join(HERE, "render.js"), html_path, out_pdf], check=True)

        preview_prefix = os.path.splitext(out_pdf)[0]
        subprocess.run(["pdftoppm", "-r", "80", "-png", "-singlefile", out_pdf, preview_prefix], check=True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print("\nPricing breakdown")
    print(f"  USD -> {currency} rate : {cfg['usd_to_cad']}")
    print(f"  mode               : {cfg.get('pricing_mode', 'markup')}")
    for label, kind, usd, cad, pct, sell in rows:
        print(f"  {label:<18} {kind:<9} {usd:>8.2f} USD -> {cad:>9.2f} {currency} cost  +{pct:g}%  -> {sell:>9.2f} {currency}")
    print(f"  supplier total     : {supplier_total:.2f} USD")
    print(f"  sell total (raw)   : {raw_total:.2f} {currency}")
    print(f"  sell total (shown) : {total_str}")
    print(f"\nPDF     : {out_pdf}")
    print(f"Preview : {preview_prefix}.png")


if __name__ == "__main__":
    main()
