#!/usr/bin/env python3
"""Flatten XD artboard graphics trees (AGC JSON) into a readable spec.

Usage: python3 agc_spec.py <json-dir> [artboard-name-substring ...]

One line per element, indented by group depth, with positions relative to the
artboard's top-left:

  T '<text>' @(x,y) <family> <style> <size>px lh<line-height> <colour> ... ranges=[...]
  S '<name>' @(x,y) <w>x<h> r=<radii> fill=<colour> stroke=<w colour> shadow=<css> op=<opacity>
  G '<name>' (group) @(x,y) op=<opacity>

Shadows are printed as CSS (blur = 2 x the stored radius). Text `ranges` lists
the ranged styles (substring, weight, size, colour), which often differ from the
text object's default style. For positioned text y is the first baseline; for
area text it is the top of the frame.
"""
import json
import os
import sys
from glob import glob


def colour(c):
    if not c:
        return None
    v = c.get("value", {})
    a = c.get("alpha", 1)
    hexa = "#%02x%02x%02x" % (round(v.get("r", 0)), round(v.get("g", 0)), round(v.get("b", 0)))
    return hexa if a == 1 else f"{hexa}@{a:.2f}"


def argb(value):
    a = ((value >> 24) & 255) / 255
    hexa = "#%02x%02x%02x" % ((value >> 16) & 255, (value >> 8) & 255, value & 255)
    return hexa if a == 1 else f"{hexa}@{a:.2f}"


def fill(style):
    f = (style or {}).get("fill")
    if not f or f.get("type") == "none":
        return None
    if f.get("type") == "solid":
        return colour(f.get("color"))
    if f.get("type") == "pattern":
        return "IMAGE"
    return f.get("type")


def stroke(style):
    s = (style or {}).get("stroke")
    if not s or s.get("type") == "none":
        return None
    return f"{s.get('width')}px {colour(s.get('color'))} {s.get('align', 'center')}"


def shadows(style):
    out = []
    for f in (style or {}).get("filters", []) or []:
        if f.get("type") == "dropShadow" and f.get("visible", True) is not False:
            for d in f["params"]["dropShadows"]:
                out.append(f"{d['dx']}px {d['dy']}px {d['r'] * 2}px {colour(d['color'])}")
    return out or None


def opacity(style):
    return f" op={style['opacity']:.2f}" if "opacity" in (style or {}) else ""


def text_ranges(node):
    raw = node["text"].get("rawText", "")
    out, i = [], 0
    for r in (node.get("meta", {}).get("ux", {}) or {}).get("rangedStyles") or []:
        segment = raw[i : i + r["length"]].replace("\n", "⏎")
        i += r["length"]
        col = argb(r["fill"]["value"]) if "fill" in r else None
        out.append(f"'{segment[:40]}':{r.get('fontStyle')}/{r.get('fontSize')}/{col}")
    return out


def walk(node, ox, oy, depth, out, origin):
    if node.get("visible") is False:
        return
    t = node.get("transform") or {}
    x, y = ox + t.get("tx", 0), oy + t.get("ty", 0)
    style = node.get("style") or {}
    pad = "  " * depth
    rx, ry = x - origin[0], y - origin[1]
    kind = node.get("type")
    if kind == "text":
        text = node["text"]
        font = style.get("font", {})
        attrs = style.get("textAttributes", {})
        frame = text.get("frame", {})
        raw = text.get("rawText", "").replace("\n", "⏎")
        ranges = text_ranges(node)
        out.append(
            f"{pad}T '{raw[:80]}' @({rx:.0f},{ry:.0f}) {font.get('family')} {font.get('style')} "
            f"{font.get('size')}px lh{attrs.get('lineHeight')} {fill(style)} "
            f"align={attrs.get('paragraphAlign', 'left')} frame={frame.get('type')} "
            f"{frame.get('width', '')}x{frame.get('height', '')}{opacity(style)}"
            + (f" ranges={ranges}" if len(ranges) > 1 else "")
        )
    elif kind == "shape":
        shape = node.get("shape", {})
        st = shape.get("type")
        if st == "rect":
            dims = f"{shape['width']:.1f}x{shape['height']:.1f} r={shape.get('r')}"
            rx, ry = rx + shape.get("x", 0), ry + shape.get("y", 0)
        elif st in ("ellipse", "circle"):
            r1 = shape.get("rx", shape.get("r"))
            r2 = shape.get("ry", shape.get("r"))
            dims = f"{st} {2 * r1:.0f}x{2 * r2:.0f}"
        elif st == "line":
            dims = f"line {shape['x1']:.0f},{shape['y1']:.0f}->{shape['x2']:.0f},{shape['y2']:.0f}"
        else:
            dims = st
        out.append(
            f"{pad}S '{node.get('name', '')}' @({rx:.0f},{ry:.0f}) {dims} fill={fill(style)} "
            f"stroke={stroke(style)} shadow={shadows(style)}{opacity(style)}"
        )
    else:
        out.append(f"{pad}G '{node.get('name', '')}' ({kind}) @({rx:.0f},{ry:.0f}){opacity(style)}")
        for child in (node.get("group") or node.get("artboard") or {}).get("children", []):
            walk(child, x, y, depth + 1, out, origin)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    json_dir, filters = sys.argv[1], sys.argv[2:]
    for path in sorted(glob(os.path.join(json_dir, "*.json"))):
        try:
            doc = json.load(open(path))
        except (ValueError, UnicodeDecodeError):
            continue
        for artboard_id, info in (doc.get("artboards") or {}).items():
            if artboard_id == "href" or not isinstance(info, dict):
                continue
            if filters and not any(f in info["name"] for f in filters):
                continue
            out = [f"##### {info['name']} {info['width']}x{info['height']} ({os.path.basename(path)})"]
            for node in doc.get("children", []):
                if node.get("id") == artboard_id:
                    out.append(f"artboard fill={fill(node.get('style'))}")
                    for child in node["artboard"]["children"]:
                        walk(child, 0, 0, 0, out, (info["x"], info["y"]))
            print("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
