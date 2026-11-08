// Regression test: preset cards render from the Repository-owned presets, not a bundled seed.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

import { renderPresetCards } from '../scripts/render-preset-cards.mjs'

const script = fileURLToPath(new URL('../scripts/render-preset-cards.mjs', import.meta.url))
const sourcePath = new URL('../catalog/studio-presets.json', import.meta.url)

test('renders supplied preset bytes and records their identity', () => {
  const original = readFileSync(sourcePath)
  const data = JSON.parse(original.toString('utf8'))
  const [target, ...others] = data.presets
  target.name = 'Renamed Repository Preset'
  target.description = 'Description changed only by the renderer regression test.'
  const modified = Buffer.from(JSON.stringify(data, null, 2) + '\n')

  const before = JSON.parse(renderPresetCards(original))
  const after = JSON.parse(renderPresetCards(modified))

  assert.ok(after.cards[target.id].includes('Renamed Repository Preset'))
  assert.ok(!before.cards[target.id].includes('Renamed Repository Preset'))
  assert.equal(after.source_sha256, createHash('sha256').update(modified).digest('hex'))
  assert.notEqual(after.source_sha256, before.source_sha256)
  for (const { id } of others) assert.equal(after.cards[id], before.cards[id])
})

test('--check passes on the real catalogue', () => {
  const run = spawnSync(process.execPath, [script, '--check'], { encoding: 'utf8' })
  assert.equal(run.status, 0, run.stderr)
})
