# Visual harness: render the code the way the design shows it

Comparing a design with code by eye is unreliable; comparing numbers is fast.
Build a throwaway harness that renders the real component with the design's
content at the artboard width, drives it through the same states as the
artboards, and saves a screenshot **and** a measurement dump for each state.

## Where to put it

Use whatever the project already has, in this order of preference:

1. Playwright component testing (`*.ct.tsx` + `playwright-ct.config.*`):
   a scratch spec next to the component. Import `test` from
   `@playwright/experimental-ct-react` directly if the project's own helper
   stubs web fonts; the comparison needs the real fonts.
2. Storybook: a scratch story plus the Playwright script below against it.
3. A dev-server route or page, plus the Playwright script below.

Name it so it is obviously temporary (`zzVisualHarness.ct.tsx`), write
screenshots outside the repo, and delete it when you're done.

## What it does

```tsx
test.use({ viewport: { width: 375, height: 900 } }) // the artboard width

test('capture', async ({ mount, page }) => {
  // Serve design images for any CMS/CDN URLs the fixture uses.
  await page.route(/cdn\.example\.com/, route => route.fulfill({ body: fs.readFileSync(...) }))
  await page.emulateMedia({ reducedMotion: 'reduce' }) // skip entrance animations
  const component = await mount(<Providers><Component {...designContent} /></Providers>)

  let step = 0
  const shot = async (label: string) => {
    await page.waitForTimeout(400)
    const name = `${OUT}/${String(step++).padStart(2, '0')}-${label}`
    await page.screenshot({ path: `${name}.png`, fullPage: true })
    fs.writeFileSync(`${name}.txt`, await page.evaluate(measure, SELECTORS))
  }

  await shot('start')
  // Then click through the same states as the artboards: start, select,
  // confirm, feedback, end... calling shot() at each.
})
```

`measure` dumps, for every element matching the selectors you care about:
`x y width height` (with `scrollY` added to `y`), `color`, `background-color`,
`opacity`, `font-weight font-size/line-height`, `margin-top`/`margin-bottom`. Add
pseudo-elements you need (`getComputedStyle(el, '::after')`) for things like
heading underlines.

```ts
const measure = (selectors: string[]) =>
  selectors.flatMap(sel =>
    [...document.querySelectorAll(sel)].map((el, i) => {
      const r = el.getBoundingClientRect()
      const cs = getComputedStyle(el)
      return `${sel}[${i}] x=${r.x.toFixed(1)} y=${(r.y + scrollY).toFixed(1)} w=${r.width.toFixed(1)} ` +
        `h=${r.height.toFixed(1)} color=${cs.color} bg=${cs.backgroundColor} op=${cs.opacity} ` +
        `font=${cs.fontWeight} ${cs.fontSize}/${cs.lineHeight} mt=${cs.marginTop} mb=${cs.marginBottom}`
    }),
  ).join('\n')
```

## Content

Copy the artboards' text into the fixture verbatim (names, questions,
paragraphs, choice labels) so lines wrap at the same words. Wrapping
differences then point at real width or padding differences, not at content.

## Comparing

Work relative to a shared anchor (the top of a panel, the first message),
not absolute page y, since the page chrome around the component rarely matches
the artboard. For each gap in the design spec, compute the same gap from the
dump and fix the CSS until they agree within about 1px. Then look at the
screenshots side by side with the rendered artboards for anything the numbers
don't cover (icons, opacity, ordering).

Keep a `before/` set from the first run so you can show what changed.
