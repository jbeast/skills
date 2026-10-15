# Reading XD share data (AGC)

What `xd_capture.mjs` saves, and the traps when turning it into CSS numbers.
Read this when `agc_spec.py` output looks odd or you need a value it doesn't print.

## Files

`json/<component-id>.<ext>`, one per CDN component the viewer fetched:

| Content type | What it is |
|---|---|
| `application/vnd.adobe.agc.graphicsTree+json` | One artboard (or a few). Has `artboards` (name, x, y, width, height keyed by artboard id) and `children` (the `artboard` node with its tree). |
| `application/vnd.adobe.uxdesign.interactions+json` | Prototype wiring: `interactions[<node id>]` → `{action, properties: {destination, transition, duration}}`. Tells you what a tap on an element leads to. |
| `application/vnd.adobe.uxdesign.globalresources+json` | Document colour swatches (`colors`), character styles (`characterStyles`), fonts. Good for building a token list. |
| `image/webp`, `image/png` | Bitmap fills (photos, avatars, diagrams). They can't be matched to the shapes that use them reliably; identify them by eye or size. |

`screens.json` lists the screens in prototype order with their artboard names.
Artboards that exist in the file but are not in that list (or that come at the
end, after the flow) are often stale drafts: weigh them lower.

## Coordinates

- Every node has `transform: {a,b,c,d,tx,ty}` relative to its parent. Top-level
  artboard children are in document coordinates; subtract the artboard's
  `x`/`y` from `artboards[id]`.
- Rect shapes also carry `shape.x`/`shape.y` inside their own transform.
- Ellipses use `cx, cy, rx, ry` (circles use `r`).

## Text

- `text.frame.type`:
  - `area`: fixed box. `ty` is the top of the box, `width`/`height` the box.
  - `positioned`: point text. `ty` is the **first baseline**, not the top; with
    `paragraphAlign: center` `tx` is the centre.
  - `autoHeight`: fixed width, grows down; like `area` but no reliable height.
- `style.font` is only the text object's default style. The real per-run styles
  are in `meta.ux.rangedStyles` (`length`, `fontStyle`, `fontSize`, `fill.value`
  as an ARGB integer). A bold-blue "Select an option." inside regular text only
  shows up there.
- `textAttributes.lineHeight` is in px. Area-text frames are often a few px
  taller than lines × line-height; trust lines × line-height for spacing.

## Fills, strokes, effects

- `style.fill.type`: `solid` (`color.value` r/g/b 0–255, optional `alpha`),
  `pattern` (bitmap), `gradient`, `none`.
- `style.stroke.align`: `inside` | `outside` | `center`. An outside or centred
  stroke draws beyond the shape's box. A selection ring drawn as a separate
  rect 6px larger with a 3px stroke is a ring that sits 3-6px outside the
  element.
- Drop shadows: `filters[].params.dropShadows[] = {dx, dy, r, color}`. **CSS blur
  = 2 × r** (XD's Specs panel shows the doubled value). Skip filters with
  `visible: false`.
- `style.opacity` on a group dims everything in it; on a single shape only that
  shape. Designers often fade a bubble's fill to 50% but leave its text at
  100%: check whether the opacity sits on the group or on the rect.

## Masks and components

- Mask groups have `meta.ux.isMaskGroup` and the mask shape in
  `meta.ux.clipPathResources.children[0]` (in group-local coordinates). Avatar
  photos are usually a large image rect clipped to a circle.
- Component (symbol) instances render from their resolved children like any
  group; `resources.meta.ux.symbols` holds the master and its states.
- Prototype artboards often stack alternate states on top of each other
  (hidden layers, duplicate text at the same position). If two elements
  overlap oddly in a rendering, compare with the viewer screenshot.

## Colour gotchas

- The same "brand blue" can appear as two slightly different hex values (for
  example `#2a71b2` vs `#2a70b2`); map both to the project's existing token.
- A panel colour drawn with partial opacity (`#f5f5f5` at 0.27) shows up as a
  different effective colour; compute it against the background before
  inventing a new token.
