# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Static CSS + JS for the catalogue site, in the nirs4all.org design system.

Uses the canonical ecosystem palette (teal-led, warm paper) with IBM Plex Sans / Inter /
JetBrains Mono, the eco-card grid, and the animated spectral strip — identical in spirit
to nirs4all.org and its subdomains. Kept as plain string constants (no f-strings) so the
CSS braces are literal.
"""

from __future__ import annotations

STYLE = """
:root {
  --teal:    #0d9488;
  --teal-d:  #0f766e;
  --teal-l:  #2dd4bf;
  --cyan:    #06b6d4;
  --cyan-d:  #0891b2;
  --indigo:  #4f46e5;
  --indigo-d:#4338ca;
  --green:   #10b981;
  --amber:   #d97706;

  --paper:    #faf7f0;
  --paper-2:  #f3efe5;
  --bg:       #ffffff;
  --bg-alt:   #f5f7fa;
  --surface:  #ffffff;
  --border:   #e2e8f0;
  --border-warm: #e8e2d3;
  --text:     #0f172a;
  --text-2:   #475569;
  --text-3:   #64748b;

  --shadow:    0 4px 16px -4px rgba(17,24,39,0.08), 0 2px 4px -2px rgba(17,24,39,0.04);
  --shadow-lg: 0 20px 40px -12px rgba(17,24,39,0.10);
  --shadow-warm: 0 18px 38px -14px rgba(120,85,30,0.16), 0 3px 8px -4px rgba(120,85,30,0.10);
  --radius:    16px;
  --radius-sm: 10px;

  --font:    'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --display: 'IBM Plex Sans', 'Inter', system-ui, sans-serif;
  --mono:    'JetBrains Mono', 'Fira Code', Consolas, monospace;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: var(--font);
  color: var(--text);
  background: var(--paper);
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}
a { color: var(--teal-d); text-decoration: none; }
a:hover { text-decoration: underline; }
h1, h2, h3, h4 { font-family: var(--display); font-weight: 600; letter-spacing: -.01em; color: var(--text); }
code, pre, .mono { font-family: var(--mono); }

.spectrum-strip {
  height: 4px;
  background: linear-gradient(90deg, var(--teal-d), var(--teal), var(--teal-l), var(--cyan), var(--teal-d));
  background-size: 300% 100%;
  animation: strip-slide 16s linear infinite;
}
@keyframes strip-slide { 0% { background-position: 0% 0; } 100% { background-position: 300% 0; } }

.container { max-width: 1180px; margin: 0 auto; padding: 0 24px; }

/* Header */
header.site {
  position: sticky; top: 0; z-index: 30;
  background: rgba(255,255,255,0.82);
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--border-warm);
}
.header-row { display: flex; align-items: center; gap: 14px; height: 60px; }
.header-row .logo { height: 28px; }
.header-row .pill-badge {
  font-family: var(--mono); font-size: .64rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: .14em; color: var(--teal-d); background: rgba(13,148,136,.07);
  border: 1px solid rgba(13,148,136,.22); border-radius: 100px; padding: 3px 10px;
}
.header-row .spacer { flex: 1; }
.header-row nav a { color: var(--text-2); font-size: .9rem; font-weight: 500; margin-left: 18px; }
.header-row nav a:hover { color: var(--teal-d); text-decoration: none; }

/* Hero */
.hero { position: relative; padding: 72px 0 56px; overflow: hidden; }
.hero::before {
  content: ''; position: absolute; inset: -30% -10% auto -10%; height: 420px; z-index: 0;
  background:
    radial-gradient(ellipse 50% 60% at 18% 0%, rgba(13,148,136,0.16), transparent 70%),
    radial-gradient(ellipse 45% 55% at 85% 10%, rgba(6,182,212,0.13), transparent 70%);
  filter: blur(16px);
}
.hero .container { position: relative; z-index: 1; }
.hero-logo { height: 58px; width: auto; display: block; margin: 0 0 26px; }
.hero .eyebrow {
  font-family: var(--mono); font-size: .72rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: .2em; color: var(--teal-d); display: inline-flex; align-items: center; gap: 10px;
}
.hero .eyebrow::before { content: ''; width: 26px; height: 1px; background: var(--teal); }
.hero h1 {
  font-size: clamp(2rem, 5vw, 3rem); line-height: 1.06; margin: 16px 0 14px; font-weight: 600;
}
.hero h1 em { font-style: normal; background: linear-gradient(120deg, var(--teal-d), var(--cyan) 55%, var(--green)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.hero p.lead { font-size: 1.12rem; color: var(--text-2); max-width: 680px; margin: 0 0 26px; }
.hero .ctas { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.btn {
  display: inline-flex; align-items: center; gap: 8px; padding: 11px 20px; border-radius: 100px;
  font-weight: 600; font-size: .92rem; border: 1px solid transparent; cursor: pointer; transition: all .2s;
}
.btn-primary { background: linear-gradient(135deg, var(--teal), var(--cyan-d)); color: #fff; box-shadow: 0 10px 24px -10px rgba(13,148,136,.5); }
.btn-primary:hover { transform: translateY(-2px); text-decoration: none; }
.btn-ghost { background: #fff; border-color: var(--border); color: var(--text); }
.btn-ghost:hover { border-color: var(--teal); color: var(--teal-d); text-decoration: none; }

/* Stats */
.stats { display: flex; flex-wrap: wrap; gap: 28px; margin-top: 36px; }
.stat .num { font-family: var(--display); font-size: 1.9rem; font-weight: 700; color: var(--teal-d); line-height: 1; }
.stat .lbl { font-family: var(--mono); font-size: .66rem; text-transform: uppercase; letter-spacing: .14em; color: var(--text-3); margin-top: 6px; }

/* Sections */
section { padding: 56px 0; position: relative; }
.section-paper {
  background: var(--paper);
  background-image: linear-gradient(rgba(20,50,48,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(20,50,48,0.035) 1px, transparent 1px);
  background-size: 52px 52px; border-top: 1px solid var(--border-warm); border-bottom: 1px solid var(--border-warm);
}
.section-head { margin-bottom: 28px; }
.section-head h2 { font-size: 1.5rem; margin: 0 0 6px; }
.section-head p { color: var(--text-2); margin: 0; }

/* Filters */
.filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 24px; }
.filters input[type=search] {
  flex: 1; min-width: 200px; padding: 9px 14px; border: 1px solid var(--border); border-radius: 100px;
  font-family: var(--font); font-size: .9rem; background: #fff;
}
.filters input[type=search]:focus { outline: none; border-color: var(--teal); box-shadow: 0 0 0 3px rgba(13,148,136,.12); }
.chipset { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  font-family: var(--mono); font-size: .68rem; font-weight: 600; padding: 5px 12px; border-radius: 100px;
  border: 1px solid var(--border); background: #fff; color: var(--text-2); cursor: pointer; transition: all .15s; text-transform: lowercase;
}
.chip.active { background: var(--teal); border-color: var(--teal); color: #fff; }
.chip:hover:not(.active) { border-color: var(--teal-l); color: var(--teal-d); }

/* Card grid */
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 20px; }
.card {
  --accent: var(--teal); position: relative; display: flex; flex-direction: column;
  background: rgba(255,255,255,0.86); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 24px 24px 20px; overflow: hidden; transition: transform .25s, border-color .25s, box-shadow .25s, background .25s;
  backdrop-filter: blur(10px);
}
.card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--accent); opacity: 0; transition: opacity .3s; }
.card:hover { transform: translateY(-3px); border-color: var(--accent); box-shadow: var(--shadow-lg); background: #fff; }
.card:hover::before { opacity: .95; }
.card a.card-link::after { content: ''; position: absolute; inset: 0; }
.card.fw-dagml { --accent: var(--indigo); }
.card-head { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.card-spark { flex: 0 0 auto; }
.card-titles { flex: 1; min-width: 0; }
.card-cat { font-family: var(--mono); font-size: .62rem; font-weight: 600; text-transform: uppercase; letter-spacing: .12em; color: var(--accent); }
.card-name { font-family: var(--display); font-size: 1.08rem; font-weight: 600; margin: 2px 0 0; }
.card-ver { font-family: var(--mono); font-size: .64rem; font-weight: 600; color: var(--text-3); background: var(--bg-alt); border: 1px solid var(--border); border-radius: 100px; padding: 2px 8px; }
.card p.desc { color: var(--text-2); font-size: .9rem; margin: 0 0 14px; line-height: 1.66; }
.badges { display: flex; flex-wrap: wrap; gap: 6px; margin-top: auto; }
.badge {
  font-family: var(--mono); font-size: .64rem; font-weight: 600; padding: 3px 10px; border-radius: 100px;
  border: 1px solid var(--border); background: var(--bg-alt); color: var(--text-3); text-transform: lowercase;
}
.badge.fw { color: var(--accent); border-color: color-mix(in srgb, var(--accent) 30%, transparent); background: color-mix(in srgb, var(--accent) 7%, transparent); }
.status {
  font-family: var(--mono); font-size: .64rem; font-weight: 600; padding: 3px 10px; border-radius: 100px;
  border: 1px dashed var(--border-warm); background: var(--paper-2); color: var(--text-3);
}
.status.ok { color: #047857; border-color: rgba(16,185,129,.4); background: rgba(16,185,129,.06); }
.status.warn { color: var(--amber); border-color: rgba(217,119,6,.4); background: rgba(217,119,6,.06); }

/* Detail page */
.detail { padding-top: 40px; }
.crumb { font-family: var(--mono); font-size: .72rem; color: var(--text-3); margin-bottom: 14px; }
.detail h1 { font-size: 2rem; margin: 4px 0 8px; }
.detail .lead { color: var(--text-2); font-size: 1.08rem; max-width: 720px; }
.detail-grid { display: grid; grid-template-columns: 1.6fr 1fr; gap: 28px; margin-top: 28px; }
@media (max-width: 860px) { .detail-grid { grid-template-columns: 1fr; } }
.panel { background: #fff; border: 1px solid var(--border); border-radius: var(--radius); padding: 22px 24px; margin-bottom: 20px; box-shadow: var(--shadow); }
.panel h3 { font-size: 1rem; margin: 0 0 12px; display: flex; align-items: center; gap: 8px; }
.panel h3::before { content: ''; width: 8px; height: 8px; border-radius: 2px; background: var(--teal); }
.kv { display: grid; grid-template-columns: max-content 1fr; gap: 6px 18px; font-size: .9rem; }
.kv dt { font-family: var(--mono); font-size: .7rem; text-transform: uppercase; letter-spacing: .1em; color: var(--text-3); }
.kv dd { margin: 0; color: var(--text); }
pre.code { background: #0b1220; color: #e2e8f0; border-radius: var(--radius-sm); padding: 16px 18px; overflow-x: auto; font-size: .82rem; line-height: 1.6; }
pre.code .cmt { color: #64748b; }
.card-md { color: var(--text-2); font-size: .94rem; }
.card-md h1, .card-md h2, .card-md h3 { margin: 18px 0 8px; }
.card-md code { background: var(--bg-alt); padding: 1px 6px; border-radius: 6px; font-size: .85em; }
.card-md pre code { background: none; padding: 0; }
.metric-row { display: flex; justify-content: space-between; font-family: var(--mono); font-size: .82rem; padding: 6px 0; border-bottom: 1px dashed var(--border-warm); }
.metric-row:last-child { border-bottom: none; }

/* Footer */
footer.site { background: radial-gradient(ellipse 120% 80% at 50% -10%, #10233a 0%, #0b1626 55%, #070e1a 100%); color: rgba(255,255,255,0.82); padding: 40px 0 28px; margin-top: 40px; }
footer.site .fam { display: flex; flex-wrap: wrap; gap: 18px; font-size: .88rem; }
footer.site a { color: rgba(255,255,255,0.86); }
footer.site .meta { font-family: var(--mono); font-size: .7rem; color: rgba(255,255,255,0.5); margin-top: 16px; letter-spacing: .06em; }

.empty { text-align: center; color: var(--text-3); padding: 40px; font-family: var(--mono); font-size: .9rem; }
@media (prefers-reduced-motion: reduce) { .spectrum-strip { animation: none; } * { transition: none !important; } }
"""

SCRIPT = """
(function () {
  var search = document.getElementById('q');
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chip'));
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card[data-id]'));
  var active = {};
  function apply() {
    var term = (search && search.value || '').toLowerCase();
    var shown = 0;
    cards.forEach(function (card) {
      var ok = true;
      for (var dim in active) {
        if (active[dim] && card.getAttribute('data-' + dim) !== active[dim] &&
            (card.getAttribute('data-' + dim) || '').split(' ').indexOf(active[dim]) < 0) { ok = false; }
      }
      if (ok && term) { ok = (card.getAttribute('data-search') || '').indexOf(term) >= 0; }
      card.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });
    var empty = document.getElementById('empty');
    if (empty) empty.style.display = shown ? 'none' : '';
  }
  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      var dim = chip.getAttribute('data-dim'); var val = chip.getAttribute('data-val');
      if (active[dim] === val) { active[dim] = null; }
      else { active[dim] = val; }
      chips.forEach(function (c) { if (c.getAttribute('data-dim') === dim) c.classList.toggle('active', active[dim] === c.getAttribute('data-val')); });
      apply();
    });
  });
  if (search) search.addEventListener('input', apply);
})();
"""
