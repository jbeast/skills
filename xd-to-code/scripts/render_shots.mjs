#!/usr/bin/env node
// Screenshot the artboard pages written by agc_render.py.
//
// Usage: node render_shots.mjs <html-dir> <out-dir> [--scale 2] [--only <name-substring>] [--clip <y>,<height>]
//
// --clip crops each artboard to a vertical band (artboard pixels), which is
// handy for looking closely at one part of a tall artboard.
// Playwright is resolved from the current working directory.
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const args = process.argv.slice(2)
const option = name => {
  const i = args.indexOf(`--${name}`)
  return i === -1 ? undefined : args.splice(i, 2)[1]
}
const scale = Number(option('scale') ?? 1)
const only = option('only')
const clip = option('clip')?.split(',').map(Number)
const [htmlDir, outDir] = args
if (!htmlDir || !outDir) {
  console.error('Usage: node render_shots.mjs <html-dir> <out-dir> [--scale 2] [--only <name>] [--clip y,height]')
  process.exit(1)
}

const require = createRequire(path.join(process.cwd(), 'noop.js'))
let chromium
for (const name of ['playwright', '@playwright/test', 'playwright-core']) {
  try {
    chromium = require(name).chromium
    break
  } catch {}
}
if (!chromium) {
  console.error('Could not resolve playwright from ' + process.cwd())
  process.exit(1)
}

fs.mkdirSync(outDir, { recursive: true })
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: scale })
const files = fs.readdirSync(htmlDir).filter(f => f.endsWith('.html') && (!only || f.includes(only)))
for (const file of files) {
  await page.goto('file://' + path.resolve(htmlDir, file))
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(200)
  const out = path.join(outDir, file.replace(/\.html$/, '.png'))
  const artboard = page.locator('#ab')
  if (clip) {
    const box = await artboard.boundingBox()
    await page.screenshot({ path: out, fullPage: true, clip: { x: box.x, y: box.y + clip[0], width: box.width, height: clip[1] } })
  } else {
    await artboard.screenshot({ path: out })
  }
  console.log(out)
}
await browser.close()
