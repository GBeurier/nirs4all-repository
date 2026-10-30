// Build-time React rendering keeps the published site and Python package JavaScript-free.
import { createHash } from 'node:crypto'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync } from 'node:fs'
import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { PipelinePresetCard } from 'nirs4all-ui/components'
import { buildPresetCardModel, getStudioPipelinePresets } from 'nirs4all-ui/pipelines'
import { Beaker, Boxes, Calculator, Cpu, Flame, FlaskConical, Gauge, GitBranch, Sparkles, Zap } from 'lucide-react'

const root = new URL('../', import.meta.url)
const source = readFileSync(new URL('catalog/studio-presets.json', root))
assert.deepEqual(JSON.parse(source).presets.map(({ repository_variants, ...preset }) => preset),
  getStudioPipelinePresets(), 'Repository presets differ from the shared Studio/Web catalogue; sync Studio presets and nirs4all-ui.')
const icons = { simple_pls: Calculator, fast_result: Zap, simple_trees_boosting: Sparkles,
  complex_pls: FlaskConical, complex_trees: Beaker, nonlinear_exploration: GitBranch,
  ultra_pls: Boxes, ultra_trees: Cpu, deep_nonlinear_exploration: Cpu, ultra_slow: Flame }
const complexityIcons = { starter: Zap, quick: Sparkles, balanced: Gauge, heavy: Boxes, exhaustive: Flame }
const cards = Object.fromEntries(JSON.parse(source).presets.map((preset) => {
  const card = buildPresetCardModel(preset)
  const ComplexityIcon = complexityIcons[card.complexityMeta.key]
  return [preset.id, renderToStaticMarkup(h(PipelinePresetCard, {
    preset,
    templateIcon: h(icons[preset.id] ?? GitBranch),
    complexityIcon: h(ComplexityIcon),
    complexityBadge: h('span', { className: `n4-preset-complexity n4-preset-${card.complexityMeta.key}` },
      h(ComplexityIcon, { size: 14 }), `${card.complexity}/10 `, h('span', null, card.complexityMeta.key)),
    previewIcons: { branch: h(GitBranch), model: h(Cpu), step: h(Boxes), generator: h(Sparkles, { color: '#f59e0b' }) },
    renderVariant: (task) => h('a', {
      className: `n4-preset-action n4-preset-action-${task}`,
      href: `pipeline/${preset.repository_variants[task]}.html`,
      'aria-label': `${preset.name} — ${task}`,
    }, task[0].toUpperCase() + task.slice(1)),
  }))]
}))
const result = JSON.stringify({
  source_sha256: createHash('sha256').update(source).digest('hex'),
  css: readFileSync(new URL(import.meta.resolve('nirs4all-ui/assets/pipeline-presets.css')), 'utf8'),
  cards,
}, null, 2) + '\n'
const output = new URL('catalog/studio-presets.cards.json', root)
if (process.argv.includes('--check')) {
  if (readFileSync(output, 'utf8') !== result) throw new Error('Preset cards are stale; run npm run build:cards')
} else {
  writeFileSync(output, result)
}
