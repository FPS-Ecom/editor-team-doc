#!/usr/bin/env python3
"""
Code-only LED preview: takes the supplier mockup (artwork only, prices cropped off),
finds the coloured LED strokes and the grey acrylic backing, and composites a glowing
version onto a plain white wall. No AI, no credits.

Usage: python3 led_preview.py --input artwork.png --out preview.png [--wall light|dim]
"""
import argparse
import colorsys

from PIL import Image, ImageChops, ImageFilter, ImageOps


def masks(im):
    """Return (stroke_mask, backing_mask) as L images from the mockup."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    stroke = Image.new("L", (w, h), 0)
    backing = Image.new("L", (w, h), 0)
    sp = stroke.load(); bp = backing.load(); px = rgb.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            hh, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if ss > 0.35 and vv > 0.45:
                sp[x, y] = 255           # coloured LED stroke
            elif ss < 0.15 and 0.55 < vv < 0.93:
                bp[x, y] = 255           # grey backing / outline
    return stroke, backing


def build(im, wall="light"):
    im = im.convert("RGB")
    # work at a comfortable size
    scale = 1200 / max(im.size)
    if scale < 1:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    w, h = im.size
    pad = round(0.12 * max(w, h))
    W, H = w + 2 * pad, h + 2 * pad

    # wall: soft vertical gradient, slightly warm
    top, bottom = ((246, 244, 240), (228, 225, 220)) if wall == "light" else ((190, 186, 180), (150, 146, 140))
    wallim = Image.new("RGB", (W, H))
    wp = wallim.load()
    for y in range(H):
        t = y / max(H - 1, 1)
        c = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            wp[x, y] = c

    stroke, backing = masks(im)
    stroke = stroke.filter(ImageFilter.MaxFilter(3))          # thicken the tube a little
    stroke_full = Image.new("L", (W, H), 0); stroke_full.paste(stroke, (pad, pad))
    backing_full = Image.new("L", (W, H), 0); backing_full.paste(backing, (pad, pad))
    backing_full = backing_full.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1))

    # drop shadow of the acrylic panel
    shadow = backing_full.filter(ImageFilter.GaussianBlur(14))
    shadow_layer = Image.new("RGB", (W, H), (0, 0, 0))
    wallim = Image.composite(shadow_layer, wallim, ImageChops.multiply(shadow, Image.new("L", (W, H), 70)))
    wallim.paste(shadow_layer, (6, 10), ImageChops.multiply(shadow, Image.new("L", (W, H), 40)))

    # clear acrylic: faint lighter panel with a soft edge
    acrylic = Image.new("RGB", (W, H), (255, 255, 255))
    wallim = Image.composite(acrylic, wallim, ImageChops.multiply(backing_full, Image.new("L", (W, H), 45)))

    # coloured glow: take the stroke colours, blur them at several radii and add them to the wall
    colour = Image.new("RGB", (W, H), (0, 0, 0))
    colour.paste(im, (pad, pad), stroke)
    colour = ImageOps.autocontrast(colour)
    out = wallim
    for radius, strength in ((3, 0.9), (10, 0.5), (28, 0.28), (70, 0.14)):
        glow = colour.filter(ImageFilter.GaussianBlur(radius))
        boost = Image.eval(glow, lambda v: min(255, int(v * strength)))
        out = ImageChops.add(out, boost)
    # bright core of the tube
    core = ImageChops.add(colour, Image.new("RGB", (W, H), (60, 60, 60)))
    core_mask = stroke_full.filter(ImageFilter.GaussianBlur(0.6))
    out = Image.composite(core, out, core_mask)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--wall", default="light", choices=["light", "dim"])
    a = ap.parse_args()
    build(Image.open(a.input), a.wall).save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()
