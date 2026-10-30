import assert from 'node:assert/strict'
import { chromium } from 'playwright-core'

const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? '/usr/bin/google-chrome',
  args: ['--no-sandbox'],
})
try {
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.route('https://**/*', (route) => route.fulfill({ body: '', contentType: 'text/plain' }))
  const base = process.env.SMOKE_URL ?? 'http://127.0.0.1:4347/'
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 800 })
    await page.goto(base)
    assert.equal(await page.locator('.n4-preset-card').count(), 10)
    assert.equal(await page.locator('.n4-preset-action').count(), 20)
    const size = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
      overflowY: getComputedStyle(document.documentElement).overflowY,
    }))
    assert.ok(size.width <= size.viewport, `Horizontal overflow at ${width}px: ${JSON.stringify(size)}`)
    assert.ok(size.height > 800, `Page should scroll at ${width}px`)
    assert.equal(size.overflowY, 'scroll')
    assert.ok(await page.locator('.n4-preset-stats dd').evaluateAll((cells) => cells.every((cell) => cell.getBoundingClientRect().height <= 20)), `Wrapped statistics at ${width}px`)
    if (width === 390) await page.screenshot({ path: 'site/presets-mobile.png', fullPage: true })
    await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' }))
    assert.ok(await page.locator('footer.site').evaluate((footer) => footer.getBoundingClientRect().bottom <= innerHeight + 1))
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(base)
  await page.locator('#q').fill('simple_pls')
  assert.equal(await page.locator('.preset-item:visible').count(), 1)
  await page.getByRole('button', { name: 'Classification', exact: true }).click()
  assert.equal(await page.locator('.preset-item:visible').count(), 1)
  assert.equal(await page.getByRole('button', { name: 'Classification', exact: true }).getAttribute('aria-pressed'), 'true')
  await page.locator('#q').fill('no-matching-preset')
  assert.equal(await page.locator('.preset-item:visible').count(), 0)
  assert.ok(await page.locator('#empty').isVisible())
  await page.locator('#q').fill('simple_pls')
  await page.locator('#q').fill('')
  await page.screenshot({ path: 'site/presets-desktop.png', fullPage: true })
  await page.getByRole('link', { name: 'Simple PLS — classification' }).click()
  assert.match(await page.locator('h1').first().innerText(), /Simple PLS \(Classification\)/)
  await page.setViewportSize({ width: 320, height: 800 })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
  assert.ok(await page.locator('pre.code').first().evaluate((pre) => pre.scrollWidth > pre.clientWidth && getComputedStyle(pre).overflowX === 'auto'))
  assert.deepEqual(errors, [])
  console.log('Preset gallery passed: 10 presets, 20 actions, filters, detail links, responsive layout, page and code scrolling.')
} finally {
  await browser.close()
}
