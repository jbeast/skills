---
name: xd-to-code
description: Make existing UI code visually match an Adobe XD design, or build new UI from one, given an XD share link (xd.adobe.com/view/...). Captures every artboard with headless Chromium, extracts exact specs (positions, colours, fonts, line heights, radii, shadows, per-run text styles), renders tall artboards whole, then measures the real component in the same states and closes the gaps. Use this whenever the user shares an xd.adobe.com link or mentions an XD file, prototype, artboards or "the design" for a component, and asks to match, implement, align with, compare against or check it, even if they don't say "XD" in the request itself. WebFetch cannot read XD links (they are a JavaScript app), so reach for this rather than guessing from a description.
---

# XD to code

Turn an Adobe XD share link into code that matches it. The method is: get the
real design data rather than eyeballing screenshots, render the code in the same
states at the same width, compare numbers, fix, repeat.

Scripts live next to this file in `scripts/`. They need Node and Python 3, plus
Playwright with Chromium, resolved from the **current working directory**. Run
them from a project that has `playwright` or `@playwright/test` installed, or
`npm i -D playwright && npx playwright install chromium` in a scratch folder.
Write everything they produce to a scratch directory, not the repo.

## 1. Pin down the job

Before capturing anything, be clear on:

- Which component(s) the design covers, and where they live in the code.
- Anything the user wants kept as it is ("keep the loader button", "don't
  touch the modal"). Treat those carve-outs as hard limits and restate them in
  your final summary.
- The target width. XD mobile artboards are usually 375px; desktop is whatever
  the artboards say. Match at that width first; keep other widths sane, not
  redesigned.

Ask only if the code location or scope is genuinely ambiguous; otherwise start.

## 2. Capture the design

```bash
node <skill>/scripts/xd_capture.mjs "<xd share url>" <scratch>/xd
```

This loads the viewer headlessly, saves every design file the viewer fetches
into `<scratch>/xd/json/`, steps through every screen (`screens.json` lists them in
prototype order with artboard names), and saves a viewer screenshot per screen
in `screens/`. It takes a minute or two for ~30 screens.

The viewer shows each artboard through a device-height window, so its
screenshots cut tall artboards off. Don't try to scroll and stitch them: the
offsets jump and the result is unreliable. Render the artboards from the data
instead:

```bash
python3 <skill>/scripts/agc_render.py <scratch>/xd/json <scratch>/xd/render          # one HTML page per artboard
node <skill>/scripts/render_shots.mjs <scratch>/xd/render <scratch>/xd/png            # full artboards
node <skill>/scripts/render_shots.mjs <scratch>/xd/render <scratch>/xd/crop --only Q4 --scale 2 --clip 2000,700
python3 <skill>/scripts/agc_spec.py <scratch>/xd/json "Q1 – 1" "End of"               # exact numbers
```

Renderings use hatched placeholders for photos and the browser's text
wrapping. Use them for layout, colour and ordering, and `agc_spec.py` for
values. `references/agc-format.md` explains the data (baseline vs top-of-frame
text, ranged text styles, stroke alignment, CSS blur = 2 × XD radius, mask
groups, opacity on groups vs shapes). Read it the first time you work through
a spec.

## 3. Read the design properly

Go through the artboards in `screens.json` order and build a short inventory
per UI element: colour, font (family/weight/size/line height), padding, radius,
shadow, the gap to its neighbours, and how it changes between states (selected,
confirmed, dimmed, error). Measure gaps from the spec, not from screenshots.

Expect the design to disagree with itself. Prototype files grow over time, so
early screens and late screens often style the same element differently, and
leftover artboards outside the flow can carry old styling. When they conflict:

- Prefer the variant used by the most screens in the flow, or by the longest
  end-to-end screen, which shows several states side by side.
- Treat artboards that appear only after the flow, or not at all in
  `screens.json`, as drafts.
- Don't stall on it: pick one, apply it consistently, and list the choice in
  your summary so the user can overrule it.

Also look for intent hidden in the data: per-run text styles (a bold
instruction appended to a question), opacity applied to a bubble's fill but not
its text, rings drawn as separate outset strokes, and image badges. The
interactions file tells you what a tap does when that matters.

## 4. Read the code

Find the component, its stylesheet(s) and any design tokens. Earlier work from
an older version of the same design is common: diff against what's there
rather than restyling from scratch. Map every XD colour to an existing token
before adding one; near-identical hexes (`#2a71b2` vs `#2a70b2`) are the same
token. Follow the project's conventions (BEM rules, token files, comment
style). If the code says how styles should be structured, obey it.

## 5. Build a visual harness and measure

Render the real component with the design's own text at the artboard width,
drive it through the same states as the artboards, and dump a screenshot plus
element measurements at each step. See `references/visual-harness.md` for a
Playwright component-test version and the measurement snippet. Keep the first
run as `before/`.

Compare relative gaps (panel top → first control, text → button, question →
choices, bubble → avatar), sizes, colours, weights and opacity against the
spec. Write the differences down as a list; that list is the work.

## 6. Make the changes

- Change values to match, preferring tokens. Add a token when a value repeats
  or carries meaning (shadow, panel colour); inline a one-off spacing.
- Keep behaviour unless the design clearly requires a change. When a visual
  change would weaken usability or accessibility (smaller hit areas, text that
  loses its accessible name, contrast), keep the visual and protect the
  behaviour: decorative overlays get `pointer-events: none`, visual-only
  instructions inside a label get `aria-hidden`, and so on.
- Don't restyle shared or global components (site-wide modals, base buttons)
  to fit one design; note the difference instead.
- Don't add comments that narrate the design ("XD: 21px from the top"). Match
  the surrounding comment density; the numbers are the code. Update existing
  comments your change makes wrong.
- Leave alone what the user carved out, even if it differs from the design.

Re-run the harness after each batch and compare again until gaps agree within
about 1px and screenshots line up.

## 7. Verify and clean up

- Run the component's unit, component and accessibility tests. Update a test
  only when it pins the old design (layout order, a removed label), and say
  which ones you changed. Treat any other failure as a bug in your change.
- Contrast or a11y tests marked as known failures: refresh their notes if your
  change moved the numbers.
- Typecheck and lint what you touched. Errors elsewhere that were already there
  are not yours to fix, but say so.
- Delete the harness, and revert incidental build artefacts
  (`*.tsbuildinfo`, caches) that the checks touched.

## 8. Report

Tell the user, briefly:

- What now matches, grouped by area (layout, typography, colour, states).
- Carve-outs you respected.
- Where the design contradicted itself and which variant you picked.
- Deliberate deviations and why (design flaws, shared components, missing CMS
  fields, accessibility).
- Test results, and which tests you updated.
- Where the before/after screenshots are.
