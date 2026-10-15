#!/usr/bin/env node
// Capture an Adobe XD share link: every design file the viewer downloads
// (artboard graphics trees, interactions, shared resources, images) plus a
// viewer screenshot and the name of every screen in prototype order.
//
// Usage: node xd_capture.mjs <xd-share-url> <out-dir>
//
// Playwright is resolved from the current working directory, so run this from
// a project that has `playwright` or `@playwright/test` installed (and its
// Chromium downloaded).
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const [url, outDir] = process.argv.slice(2)
if (!url || !outDir) {
  console.error('Usage: node xd_capture.mjs <xd-share-url> <out-dir>')
  process.exit(1)
}

const require = createRequire(path.join(process.cwd(), 'noop.js'))
const loadChromium = () => {
  for (const name of ['playwright', '@playwright/test', 'playwright-core']) {
    try {
      return require(name).chromium
    } catch {}
  }
  console.error('Could not resolve playwright from ' + process.cwd())
  process.exit(1)
}
const chromium = loadChromium()

const jsonDir = path.join(outDir, 'json')
const screensDir = path.join(outDir, 'screens')
fs.mkdirSync(jsonDir, { recursive: true })
fs.mkdirSync(screensDir, { recursive: true })

const extensionFor = contentType => {
  if (contentType.includes('json')) return 'json'
  if (contentType.includes('webp')) return 'webp'
  if (contentType.includes('png')) return 'png'
  if (contentType.includes('jpeg') || contentType.includes('jpg')) return 'jpg'
  if (contentType.includes('svg')) return 'svg'
  return 'bin'
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } })
const components = {}

// The viewer fetches each design component from the sharing CDN by id.
page.on('response', async response => {
  const componentId = response.url().match(/component_id=([^&]+)/)?.[1]
  if (!componentId || components[componentId]) return
  const contentType = response.headers()['content-type'] || ''
  try {
    const body = await response.body()
    const file = `${componentId}.${extensionFor(contentType)}`
    fs.writeFileSync(path.join(jsonDir, file), body)
    components[componentId] = { file, contentType }
  } catch {}
})

await page.goto(url, { waitUntil: 'networkidle', timeout: 120_000 })
await page.waitForTimeout(5000)

const dismissPopups = async () => {
  try {
    await page.getByRole('button', { name: 'OK' }).click({ timeout: 800 })
  } catch {}
}

const screens = []
for (let index = 1; index <= 500; index++) {
  await dismissPopups()
  const bodyText = await page.innerText('body')
  const lines = bodyText.split('\n').map(line => line.trim()).filter(Boolean)
  const counter = bodyText.match(/(\d+) of (\d+)/)
  // The breadcrumb reads "<document name> > <artboard name>".
  const name = lines[1] ?? ''
  const file = `${String(index).padStart(2, '0')}.png`
  await page.screenshot({ path: path.join(screensDir, file) })
  screens.push({ index, name, url: page.url(), screenshot: `screens/${file}` })
  console.log(`${index}${counter ? `/${counter[2]}` : ''} ${name}`)
  if (counter && Number(counter[1]) >= Number(counter[2])) break
  await page.keyboard.press('ArrowRight')
  await page.waitForTimeout(3000)
}

await page.waitForTimeout(2000)
fs.writeFileSync(path.join(outDir, 'screens.json'), JSON.stringify(screens, null, 2))
fs.writeFileSync(path.join(outDir, 'components.json'), JSON.stringify(components, null, 2))
console.log(`Saved ${Object.keys(components).length} components and ${screens.length} screens to ${outDir}`)
await browser.close()
