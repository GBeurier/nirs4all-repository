// Build-time React rendering keeps the published site and Python package JavaScript-free.
import { createHash } from 'node:crypto'
import { readFileSync, realpathSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { PipelinePresetCard } from 'nirs4all-ui/components'
import { buildPresetCardModel } from 'nirs4all-ui/pipelines'
import { Beaker, Boxes, Calculator, Cpu, Flame, FlaskConical, Gauge, GitBranch, Sparkles, Zap } from 'lucide-react'

const icons = { simple_pls: Calculator, fast_result: Zap, simple_trees_boosting: Sparkles,
  complex_pls: FlaskConical, complex_trees: Beaker, nonlinear_exploration: GitBranch,
  ultra_pls: Boxes, ultra_trees: Cpu, deep_nonlinear_exploration: Cpu, ultra_slow: Flame }
const complexityIcons = { starter: Zap, quick: Sparkles, balanced: Gauge, heavy: Boxes, exhaustive: Flame }

/**
 * Render the Repository-owned preset snapshot into the generated cards document.
 *
 * @param {Uint8Array | string} sourceBytes Exact bytes of `catalog/studio-presets.json`.
 * @returns {string} The `catalog/studio-presets.cards.json` text for those bytes.
 */
export function renderPresetCards(sourceBytes) {
  const source = Buffer.from(sourceBytes)
  const cards = Object.fromEntries(JSON.parse(source.toString('utf8')).presets.map((preset) => {
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
  return JSON.stringify({
    source_sha256: createHash('sha256').update(source).digest('hex'),
    css: readFileSync(new URL(import.meta.resolve('nirs4all-ui/assets/pipeline-presets.css')), 'utf8'),
    cards,
  }, null, 2) + '\n'
}

if (process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))) {
  const root = new URL('../', import.meta.url)
  const result = renderPresetCards(readFileSync(new URL('catalog/studio-presets.json', root)))
  const output = new URL('catalog/studio-presets.cards.json', root)
  if (process.argv.includes('--check')) {
    if (readFileSync(output, 'utf8') !== result) throw new Error('Preset cards are stale; run npm run build:cards')
  } else {
    writeFileSync(output, result)
  }
}
