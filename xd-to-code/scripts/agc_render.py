#!/usr/bin/env python3
"""Render XD artboard graphics trees (AGC JSON) to standalone HTML pages.

Usage: python3 agc_render.py <json-dir> <out-dir> [artboard-name-substring ...]

Writes one <artboard-name>.html per artboard, each with a #ab element sized to
the artboard. Screenshot them with render_shots.mjs. The XD viewer only shows a
device-height window of each artboard, so this is how to see a tall artboard
whole.

Approximations: image fills are drawn as a hatched placeholder (the image
assets cannot be matched to fills reliably), text wraps with the browser's
metrics rather than XD's, and fonts load from Google Fonts. Use the rendering
for layout and colour, and agc_spec.py for exact numbers.
"""
import html
import json
import os
import re
import sys
from glob import glob

WEIGHTS = {"thin": 100, "light": 300, "regular": 400, "medium": 500, "semibold": 600, "bold": 700, "extrabold": 800, "black": 900}
PLACEHOLDER = "repeating-linear-gradient(45deg,#c9d3dc 0 6px,#b7c2cc 6px 12px)"


def weight(style):
    key = (style or "regular").lower().replace("italic", "").replace(" ", "").replace("-", "") or "regular"
    return WEIGHTS.get(key, 400)


def rgba(c):
    if not c:
        return "transparent"
    v = c.get("value", {})
    return f"rgba({v.get('r', 0)},{v.get('g', 0)},{v.get('b', 0)},{c.get('alpha', 1)})"


def argb(value):
    return f"rgba({(value >> 16) & 255},{(value >> 8) & 255},{value & 255},{((value >> 24) & 255) / 255:.3f})"


def fill_css(style):
    f = (style or {}).get("fill")
    if not f or f.get("type") == "none":
        return "transparent"
    if f.get("type") == "solid":
        return rgba(f.get("color"))
    if f.get("type") == "pattern":
        return PLACEHOLDER
    return "#ccc"


def shadows(style):
    out = []
    for f in (style or {}).get("filters", []) or []:
        if f.get("type") == "dropShadow" and f.get("visible", True) is not False:
            for d in f["params"]["dropShadows"]:
                out.append(f"{d['dx']}px {d['dy']}px {d['r'] * 2}px {rgba(d['color'])}")
    return out


class Renderer:
    def __init__(self):
        self.fonts = {}

    def note_font(self, family, style):
        if family:
            self.fonts.setdefault(family, set()).add((weight(style), "italic" in (style or "").lower()))

    def shape(self, style, shape):
        fill = fill_css(style)
        s = style.get("stroke") or {}
        sw = s.get("width", 0) if s.get("type", "none") != "none" else 0
        sc = rgba(s.get("color")) if sw else "none"
        box_shadows = shadows(style)
        op = style.get("opacity", 1)
        kind = shape.get("type")
        if kind == "rect":
            r = shape.get("r") or 0
            radii = r if isinstance(r, list) else [r] * 4
            if sw:
                align = s.get("align", "center")
                if align == "inside":
                    box_shadows.append(f"inset 0 0 0 {sw}px {sc}")
                elif align == "outside":
                    box_shadows.append(f"0 0 0 {sw}px {sc}")
                else:
                    box_shadows += [f"inset 0 0 0 {sw / 2}px {sc}", f"0 0 0 {sw / 2}px {sc}"]
            return (
                f'<div style="position:absolute;left:{shape.get("x", 0)}px;top:{shape.get("y", 0)}px;'
                f'width:{shape["width"]}px;height:{shape["height"]}px;background:{fill};'
                f'border-radius:{"px ".join(str(x) for x in radii)}px;'
                f'box-shadow:{",".join(box_shadows) or "none"};opacity:{op}"></div>'
            )
        if kind in ("ellipse", "circle"):
            rx = shape.get("rx", shape.get("r"))
            ry = shape.get("ry", shape.get("r"))
            cx, cy = shape.get("cx", rx), shape.get("cy", ry)
            if sw:
                box_shadows.append(f"inset 0 0 0 {sw}px {sc}")
            return (
                f'<div style="position:absolute;left:{cx - rx}px;top:{cy - ry}px;width:{2 * rx}px;'
                f'height:{2 * ry}px;border-radius:50%;background:{fill};'
                f'box-shadow:{",".join(box_shadows) or "none"};opacity:{op}"></div>'
            )
        drop = " ".join(f"drop-shadow({x})" for x in box_shadows)
        svg_style = f"position:absolute;left:0;top:0;overflow:visible;opacity:{op};" + (f"filter:{drop};" if drop else "")
        svg_fill = "#bbb" if fill == PLACEHOLDER else fill
        if kind == "line":
            return (
                f'<svg width="1" height="1" style="{svg_style}"><line x1="{shape["x1"]}" y1="{shape["y1"]}" '
                f'x2="{shape["x2"]}" y2="{shape["y2"]}" stroke="{sc}" stroke-width="{sw}"/></svg>'
            )
        if kind in ("path", "compound"):
            rule = ' fill-rule="evenodd"' if kind == "compound" else ""
            return (
                f'<svg width="1" height="1" style="{svg_style}"><path d="{shape.get("path", "")}" '
                f'fill="{svg_fill}"{rule} stroke="{sc}" stroke-width="{sw}"/></svg>'
            )
        return ""

    def text(self, node, style):
        text = node["text"]
        font = style.get("font", {})
        attrs = style.get("textAttributes", {})
        raw = text.get("rawText", "")
        frame = text.get("frame", {})
        align = attrs.get("paragraphAlign", "left")
        size = font.get("size", 16)
        line_height = attrs.get("lineHeight") or round(size * 1.36)
        self.note_font(font.get("family"), font.get("style"))
        spans, i = [], 0
        for r in (node.get("meta", {}).get("ux", {}) or {}).get("rangedStyles") or []:
            segment = raw[i : i + r["length"]]
            i += r["length"]
            font_style = r.get("fontStyle", font.get("style", "Regular"))
            family = r.get("fontFamily", font.get("family"))
            self.note_font(family, font_style)
            colour = argb(r["fill"]["value"]) if "fill" in r else rgba(style.get("fill", {}).get("color"))
            css = (
                f"font-family:'{family}';font-size:{r.get('fontSize', size)}px;font-weight:{weight(font_style)};"
                f"{'font-style:italic;' if 'italic' in font_style.lower() else ''}color:{colour};"
                f"{'text-decoration:underline;' if r.get('underline') else ''}"
            )
            spans.append(f'<span style="{css}">{html.escape(segment)}</span>')
        if i < len(raw) or not spans:
            spans.append(html.escape(raw[i:]))
        base = (
            f"font-family:'{font.get('family')}';font-size:{size}px;font-weight:{weight(font.get('style'))};"
            f"line-height:{line_height}px;color:{rgba(style.get('fill', {}).get('color'))};"
            f"white-space:pre-wrap;text-align:{align};"
        )
        if frame.get("type") == "area":
            return f'<div style="position:absolute;left:0;top:0;width:{frame["width"]}px;{base}">{"".join(spans)}</div>'
        # Positioned and auto-height text: y is the first baseline. Place the
        # line box so its baseline lands there (Open Sans-like metrics).
        top = -((line_height - 1.362 * size) / 2 + 1.069 * size)
        shift = {"center": "translateX(-50%)", "right": "translateX(-100%)"}.get(align, "none")
        if frame.get("type") == "autoHeight" and frame.get("width"):
            sizing = f"width:{frame['width']}px;"
        else:
            sizing = "white-space:pre;width:max-content;"
        return (
            f'<div style="position:absolute;left:0;top:{top}px;{base}{sizing}transform:{shift}">'
            f'{"".join(spans)}</div>'
        )

    def node(self, node):
        if node.get("visible") is False:
            return ""
        t = node.get("transform") or {}
        style = node.get("style") or {}
        matrix = f'matrix({t.get("a", 1)},{t.get("b", 0)},{t.get("c", 0)},{t.get("d", 1)},{t.get("tx", 0)},{t.get("ty", 0)})'
        kind = node.get("type")
        if kind == "shape":
            inner = self.shape(style, node["shape"])
        elif kind == "text":
            inner = self.text(node, style)
        else:
            inner = "".join(self.node(c) for c in (node.get("group") or {}).get("children", []))
            clip = (node.get("meta", {}).get("ux", {}) or {}).get("clipPathResources")
            if clip:
                inner = self.clip(clip, inner)
            if "opacity" in style:
                inner = f'<div style="opacity:{style["opacity"]}">{inner}</div>'
        return f'<div style="position:absolute;left:0;top:0;transform-origin:0 0;transform:{matrix}">{inner}</div>'

    def clip(self, clip, inner):
        shape_node = clip["children"][0]
        t = shape_node.get("transform", {})
        ox, oy = t.get("tx", 0), t.get("ty", 0)
        shape = shape_node["shape"]
        if shape.get("type") in ("ellipse", "circle"):
            rx = shape.get("rx", shape.get("r"))
            ry = shape.get("ry", shape.get("r"))
            path = f'ellipse({rx}px {ry}px at {ox + shape.get("cx", rx)}px {oy + shape.get("cy", ry)}px)'
        elif shape.get("type") == "rect":
            x0, y0 = ox + shape.get("x", 0), oy + shape.get("y", 0)
            x1, y1 = x0 + shape["width"], y0 + shape["height"]
            path = f"polygon({x0}px {y0}px,{x1}px {y0}px,{x1}px {y1}px,{x0}px {y1}px)"
        else:
            path = f"path('{shape.get('path', '')}')"
        return f'<div style="position:absolute;left:0;top:0;width:4000px;height:8000px;clip-path:{path}">{inner}</div>'

    def fonts_link(self):
        families = []
        for family, variants in sorted(self.fonts.items()):
            if not family or family.lower().startswith(("sf ", ".sf", "helvetica", "arial")):
                continue
            specs = sorted({(int(italic), w) for w, italic in variants} | {(0, 400)})
            axis = ";".join(f"{i},{w}" for i, w in specs)
            families.append(f"family={family.replace(' ', '+')}:ital,wght@{axis}")
        if not families:
            return ""
        return f'<link href="https://fonts.googleapis.com/css2?{"&".join(families)}&display=block" rel="stylesheet">'


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "artboard"


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    json_dir, out_dir, filters = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs(out_dir, exist_ok=True)
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
            artboard = next((c for c in doc.get("children", []) if c.get("id") == artboard_id), None)
            if not artboard:
                continue
            renderer = Renderer()
            body = "".join(renderer.node(c) for c in artboard["artboard"]["children"])
            page = f"""<!doctype html><html><head><meta charset="utf-8">{renderer.fonts_link()}
<style>html,body{{margin:0}}#ab{{position:relative;width:{info['width']}px;height:{info['height']}px;overflow:hidden;background:{fill_css(artboard.get('style'))}}}</style></head>
<body><div id="ab"><div style="position:absolute;left:0;top:0;transform:translate({-info['x']}px,{-info['y']}px)">{body}</div></div></body></html>"""
            out = os.path.join(out_dir, safe_name(info["name"]) + ".html")
            with open(out, "w") as fh:
                fh.write(page)
            print(f"{out} {info['width']}x{info['height']}")


if __name__ == "__main__":
    main()
