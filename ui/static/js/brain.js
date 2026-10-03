// Brain-state panels for the live console: decision, neuromodulators, energy &
// sensory gate, criticality and path integration, plus the readout table.

import { AvalancheHistogram, drawKappaGauge, drawSparkline } from './charts.js';
import { MODULATORS, T } from './theme.js';
import { clamp, clear, deg, el, fitCanvas, fmt, fmtAny, fmtInt, fmtSigned, headingDeg, wrapAngle } from './util.js';

const ACTIONS = [
  ['FORWARD', 'Forward'],
  ['TURN_LEFT', 'Turn left'],
  ['TURN_RIGHT', 'Turn right'],
  ['REST', 'Rest'],
];

/** A diverging bar: zero in the middle, fills left (negative) or right (positive). */
function divergingBar(fill, value, scale) {
  const f = clamp(value / scale, -1, 1);
  fill.style.left = `${50 + Math.min(0, f) * 50}%`;
  fill.style.width = `${Math.abs(f) * 50}%`;
}

// Microsleep replay: which step of the recent path (counted back from sleep
// onset) is being replayed. Legacy replay (value_memory.replay_recent off) has
// no span and shows the TRN buffer index instead.
function replayText(r) {
  if (r.span > 0) return `Replaying ${r.back} of ${r.span} steps back`;
  return r.cell ? `Replaying step ${r.index}` : 'Replay (nothing to replay)';
}

/** A status chip: colour + icon + label, never colour alone. */
export function chip(status, icon, label) {
  return el('span', { class: 'chip', dataset: { status } }, el('span', { class: 'chip-icon', 'aria-hidden': 'true', text: icon }), label);
}

// ---------------------------------------------------------------- decision

export class DecisionPanel {
  constructor(host) {
    clear(host);
    this.rows = {};
    const bars = el('div', { class: 'bars' });
    for (const [key, label] of ACTIONS) {
      const fill = el('div', { class: 'bar-fill' });
      const val = el('span', { class: 'bar-val num' });
      const name = el('span', { class: 'bar-label', text: label });
      const row = el('div', { class: 'bar-row' }, name, el('div', { class: 'bar-track' }, fill), val);
      bars.append(row);
      this.rows[key] = { row, fill, val, name, label };
    }
    this.pull = {};
    const pull = el('div', { class: 'bars' });
    for (const [key, label] of [['ahead', 'Forward'], ['left', 'Turn left'], ['right', 'Turn right']]) {
      const fill = el('div', { class: 'bar-fill' });
      const val = el('span', { class: 'bar-val num' });
      pull.append(el('div', { class: 'bar-row' }, el('span', { class: 'bar-label', text: label }), el('div', { class: 'bar-track' }, fill), val));
      this.pull[key] = { fill, val };
    }
    this.pullNote = el('span', { class: 'muted' });
    // Why memory or pain is (partly) switched off right now; hidden when none is.
    this.mods = el('div', { class: 'crit-line decision-mods' });
    this.gain = el('div', { class: 'crit-line' });
    host.append(
      bars,
      el('div', { class: 'subhead' }, el('span', { text: 'Memory steer (value map)' }), this.pullNote),
      pull,
      this.mods,
      el('div', { class: 'subhead' }, el('span', { text: 'Criticality → vision gain' }), el('span', { class: 'muted', text: 'off at defaults' })),
      this.gain,
    );
  }

  update(action) {
    const scores = action.scores || {};
    const scale = Math.max(0.5, ...Object.values(scores).map((v) => Math.abs(v)));
    for (const [key] of ACTIONS) {
      const r = this.rows[key];
      const v = scores[key] ?? 0;
      const chosen = action.name === key;
      r.row.dataset.chosen = String(chosen);
      divergingBar(r.fill, v, scale);
      r.val.textContent = fmtSigned(v, 2);
      r.row.title = chosen ? `${r.label}: chosen (highest score)` : r.label;
    }
    const [ahead, left, right] = action.value || [0, 0, 0];
    const any = Math.abs(ahead) + Math.abs(left) + Math.abs(right) > 1e-6;
    for (const [key, v] of [['ahead', ahead], ['left', left], ['right', right]]) {
      const p = this.pull[key];
      p.fill.className = `bar-fill ${v >= 0 ? 'pos' : 'neg'}`;
      divergingBar(p.fill, v, 1);
      p.val.textContent = any ? fmtSigned(v, 2) : '—';
    }
    // These are the value signals added to each action's score (times Memory steering),
    // after cue and wall gating. Under split steering they are commands: a turn toward
    // the side that beats straight on, with Forward giving way; under max-norm they
    // are each direction's advantage over here, scaled to the largest.
    const gate = action.cue_gate ?? 1;
    const split = (action.steer ?? 'split') === 'split';
    this.pullNote.textContent = any
      ? (split ? 'blue = memory favours this action' : 'blue = better than here')
      : gate <= 0 ? 'muted' : split ? 'no steer: no clearly better direction' : 'nothing learned nearby yet';
    const lines = [];
    if (gate < 1) {
      lines.push(
        gate <= 0
          ? el('div', {}, 'Memory muted: target in view')
          : el('div', {}, 'Memory dimmed: target in view ', el('span', { class: 'num', text: `×${fmt(gate, 2)}` })),
      );
    }
    if (action.goal_vector) {
      lines.push(el('div', {}, 'Value map flat here: turning toward the remembered goal, oracle homing (goal vector)'));
    }
    const wall = action.wall_gate ?? 1;
    if (wall < 0.99) {
      lines.push(el('div', {}, 'Memory\'s push to go straight dimmed: wall ahead ', el('span', { class: 'num', text: `×${fmt(wall, 2)}` })));
    }
    const freeze = action.freeze ?? 1;
    if (freeze < 0.99) {
      lines.push(el('div', {}, 'Pain freeze habituating: pain → rest drive ', el('span', { class: 'num', text: `×${fmt(freeze, 2)}` })));
    }
    this.mods.replaceChildren(...lines);
    this.mods.hidden = lines.length === 0;
    // crit_gain is exp(-((κ - 1) / 0.3)²), computed every tick. It multiplies vision drive
    // only in proportion to the "Criticality → sensory gain" parameter, which is 0 at
    // defaults; at the default coupling 0.25 it stays within 0.93-1.0 after warm-up and
    // changes no decision even at full strength (tools/probes/dormant_couplings).
    this.gain.replaceChildren(
      'Gain from κ ',
      el('span', { class: 'num', text: `×${fmt(action.crit_gain, 2)}` }),
      ' (peaks at κ = 1, width 0.3). ',
      el('span', {
        class: 'hint',
        text: 'It scales vision only in proportion to "Criticality → sensory gain", which is 0 at defaults, so this is a readout. At coupling 0.25 it stays within 0.93–1.0 after warm-up and changes no decision even at 1.0.',
      }),
    );
  }
}

// ---------------------------------------------------------- neuromodulators

export class ModulatorPanel {
  constructor(host) {
    clear(host);
    this.rows = MODULATORS.map((m) => {
      const dot = el('span', { class: 'dot' });
      const value = el('span', { class: 'mod-value num' });
      const spark = el('canvas', { class: 'mod-spark', role: 'img', 'aria-label': `${m.name} recent trend` });
      const row = el(
        'div',
        { class: 'mod-row' },
        el('div', { class: 'mod-name' }, dot, m.name, el('span', { class: 'mod-abbr', text: m.mod }), value),
        spark,
        el('div', { class: 'mod-role', text: m.role }),
      );
      host.append(row);
      return { m, dot, value, spark };
    });
    // What the four traces are (core/neuromodulation.py), so the names are not over-read.
    this.note = el('p', {
      class: 'hint',
      text: 'Four scalar traces, not models of these systems: DA = reward − its running mean; ACh = the novelty bit (1 when the observation checksum changed) and NE = ½ pain + ½ that bit; 5HT = the running mean itself, lagging DA\'s input. Each enters action selection through one small gain.',
    });
    this.note.style.margin = '8px 0 0';
    host.append(this.note);
    this.history = {};
  }

  update(mod, history) {
    for (const r of this.rows) {
      r.dot.style.background = T[r.m.key];
      const v = mod[r.m.mod] ?? 0;
      r.value.textContent = fmt(v, 2);
      drawSparkline(r.spark, history[r.m.key] || [], T[r.m.key]);
    }
  }
}

// ------------------------------------------------------------------- energy

export class EnergyPanel {
  constructor(host) {
    clear(host);
    const meter = (label) => {
      const fill = el('div', { class: 'meter-fill' });
      const val = el('span', { class: 'meter-val num' });
      host.append(el('div', { class: 'meter-row' }, el('span', { class: 'meter-label', text: label }), el('div', { class: 'meter' }, fill), val));
      return { fill, val };
    };
    this.atp = meter('ATP');
    this.gly = meter('Glycogen');
    this.motor = meter('Motor scale');
    this.chips = el('div', { class: 'chips' });
    this.note = el('p', { class: 'hint' });
    this.note.style.margin = '8px 0 0';
    host.append(this.chips, this.note);
  }

  update(f) {
    const set = (m, v) => {
      m.fill.style.width = `${clamp(v, 0, 1) * 100}%`;
      m.val.textContent = fmt(v, 2);
    };
    set(this.atp, f.energy.atp);
    const store = f.energy.glycogen_max || 3;
    this.gly.fill.style.width = `${clamp(f.energy.glycogen / store, 0, 1) * 100}%`;
    this.gly.val.textContent = fmt(f.energy.glycogen, 2);
    this.gly.val.title = `of a ${fmt(store, 1)} store`;
    set(this.motor, f.energy.scale);
    const gate = f.trn.state;
    const chips = [];
    if (gate === 'OPEN') chips.push(chip('good', '✓', 'Gate open'));
    else if (gate === 'NARROW') chips.push(chip('warning', '!', 'Gate narrowed'));
    else chips.push(chip('critical', '✕', 'Gate closed'));
    if (f.microsleep.active) chips.push(chip('warning', 'z', `Microsleep · ${f.microsleep.remaining} ticks left`));
    else chips.push(chip('neutral', '•', 'Awake'));
    if (f.replay.active) chips.push(chip('neutral', '↺', replayText(f.replay)));
    if (f.energy.pacing) chips.push(chip('neutral', '◐', 'Resting to recover'));
    this.chips.replaceChildren(...chips);
    this.note.textContent =
      gate === 'OPEN'
        ? 'Senses and path integration at full strength.'
        : gate === 'NARROW'
          ? 'Tired: senses are attenuated and path integration under-counts movement.'
          : 'Senses are off; the brain is cut off from the world.';
  }
}

// -------------------------------------------------------------- criticality

export class CriticalityPanel {
  constructor(host) {
    clear(host);
    this.lattice = el('canvas', { class: 'lattice', role: 'img', 'aria-label': 'Criticality lattice: cells firing in the current avalanche' });
    this.kappa = el('div', { class: 'kappa-big num' });
    this.regime = el('div', {
      title: 'The κ estimator (reference exponent 1.5) read against the 0.85–1.05 band, not the lattice\'s critical point: at the default coupling 0.25 the lattice is subcritical; it is critical at coupling 0.5.',
    });
    this.sigma = el('div', { class: 'crit-line' });
    this.count = el('div', { class: 'crit-line' });
    const sw = (cls) => {
      const s = el('span', { class: `sw ${cls}` });
      return s;
    };
    this.keyFront = sw('');
    this.keyFoot = sw('');
    this.keyRest = sw('');
    const key = el(
      'div',
      { class: 'lattice-key' },
      el('span', {}, this.keyFront, 'firing now'),
      el('span', {}, this.keyFoot, 'fired this avalanche'),
    );
    this.gauge = el('canvas', { class: 'gauge', role: 'img', 'aria-label': 'Kappa gauge' });
    host.append(
      el('div', { class: 'crit-top' }, el('div', {}, this.lattice, key), el('div', { class: 'crit-stats' }, this.kappa, this.regime, this.sigma, this.count)),
      this.gauge,
      el('div', {
        class: 'crit-line',
        text: 'κ compares the avalanche-size distribution with a reference power law of exponent 1.5 (Shew et al. 2009); the chip calls κ 0.85–1.05 "near-critical". The lattice is bond percolation on a 16 × 16 torus: subcritical at the default coupling 0.25 (κ settles near 0.91 after warm-up), spanning avalanches from 0.35, critical at 0.5, above the slider\'s range.',
      }),
      el('div', { class: 'subhead' }, el('span', { text: 'Avalanche sizes' }), el('span', { class: 'muted', text: 'dashed line: reference slope −1.5' })),
    );
    this.hist = new AvalancheHistogram(host);
    this.last = null;
  }

  update(crit) {
    this.last = crit;
    const n = crit.size;
    const { ctx, w } = fitCanvas(this.lattice, 148, 148);
    const cell = w / n;
    ctx.clearRect(0, 0, w, w);
    ctx.fillStyle = T.grid;
    ctx.fillRect(0, 0, w, w);
    const paint = (cells, color) => {
      ctx.fillStyle = color;
      for (const [i, j] of cells) ctx.fillRect(i * cell + 1, j * cell + 1, cell - 2, cell - 2);
    };
    ctx.fillStyle = T.floor;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) ctx.fillRect(i * cell + 1, j * cell + 1, cell - 2, cell - 2);
    paint(crit.cells, T['ink-3']);
    paint(crit.front, T['ink-1']);
    this.keyFront.style.background = T['ink-1'];
    this.keyFoot.style.background = T['ink-3'];

    const measuring = crit.regime === 'measuring';
    this.kappa.replaceChildren(el('span', { class: 'kappa-sym', text: 'κ' }), measuring ? '—' : fmt(crit.kappa, 2));
    const chips = {
      'near-critical': ['neutral', '≈', 'κ 0.85–1.05 (estimator band)'],
      subcritical: ['neutral', '↓', 'κ < 0.85'],
      supercritical: ['neutral', '↑', 'κ > 1.05'],
      measuring: ['neutral', '…', 'Measuring'],
    };
    const [st, ic, lb] = chips[crit.regime] || chips.measuring;
    this.regime.replaceChildren(chip(st, ic, lb));
    this.sigma.replaceChildren('Branching ratio σ = 4 × ', el('span', { class: 'num', text: fmt(crit.coupling, 2) }), ' = ', el('span', { class: 'num', text: fmt(crit.sigma, 2) }), ' (mean-field; this lattice is critical at coupling 0.5)');
    this.count.replaceChildren(el('span', { class: 'num', text: fmtInt(crit.n) }), measuring ? ' avalanches (need 20 for κ)' : ' avalanches measured');
    drawKappaGauge(this.gauge, crit.kappa, measuring);
  }

  setHistogram(h) {
    this.hist.set(h);
  }

  redraw() {
    if (this.last) this.update(this.last);
    this.hist.render();
  }
}

// --------------------------------------------------------- path integration

export class CompassPanel {
  constructor(host) {
    clear(host);
    this.canvas = el('canvas', { class: 'compass', role: 'img', 'aria-label': 'True heading versus estimated heading' });
    this.drift = el('span', { class: 'num' });
    this.hdErr = el('span', { class: 'num' });
    this.place = el('span', { class: 'num' });
    host.append(
      el(
        'div',
        { class: 'compass-wrap' },
        this.canvas,
        el(
          'div',
          { class: 'compass-key' },
          el('div', {}, el('span', { class: 'needle-key' }), 'True heading'),
          el('div', {}, el('span', { class: 'needle-key est' }), 'Estimated heading'),
          el('div', {}, 'Position drift ', this.drift),
          el('div', {}, 'Heading error ', this.hdErr),
          el('div', {}, 'Place cell ', this.place),
        ),
      ),
    );
    this.last = null;
  }

  update(agent, placeId) {
    this.last = [agent, placeId];
    const { ctx, w, h } = fitCanvas(this.canvas, 120, 120);
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2;
    const cy = h / 2;
    const r = w / 2 - 14;
    ctx.strokeStyle = T.grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = T['ink-3'];
    ctx.font = '10px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('+y', cx, cy - r - 8);
    ctx.fillText('+x', cx + r + 8, cy);
    const needle = (angle, color, dash, len) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.setLineDash(dash);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(angle) * len, cy - Math.sin(angle) * len);
      ctx.stroke();
      ctx.setLineDash([]);
    };
    needle(agent.est_heading, T['ink-2'], [4, 3], r - 4);
    needle(agent.heading, T['ink-1'], [], r);
    ctx.fillStyle = T['ink-1'];
    ctx.beginPath();
    ctx.arc(cx, cy, 3, 0, Math.PI * 2);
    ctx.fill();
    this.drift.textContent = `${fmt(Math.hypot(agent.est_x - agent.x, agent.est_y - agent.y), 2)} m`;
    this.hdErr.textContent = `${fmt(Math.abs(deg(wrapAngle(agent.est_heading - agent.heading))), 0)}°`;
    this.place.textContent = fmtAny(placeId);
  }

  redraw() {
    if (this.last) this.update(...this.last);
  }
}

// ------------------------------------------------------------ readout table

/** Render a grouped key/value table: groups = [[title, [[label, value], ...]], ...]. */
export function renderTable(table, groups) {
  const rows = [];
  for (const [title, items] of groups) {
    rows.push(el('tr', { class: 'group' }, el('th', { colspan: 2, scope: 'colgroup', text: title })));
    for (const [label, value] of items) rows.push(el('tr', {}, el('th', { scope: 'row', text: label }), el('td', { text: typeof value === 'string' ? value : fmtAny(value) })));
  }
  table.replaceChildren(el('tbody', {}, rows));
}

export function frameTableGroups(f) {
  const a = f.agent;
  return [
    ['Body', [['x, y (m)', `${fmt(a.x, 2)}, ${fmt(a.y, 2)}`], ['Heading', `${fmt(headingDeg(a.heading), 1)}°`], ['Action', f.action.name], ['Reward', fmtSigned(f.reward, 3)]]],
    ['Decision', [['Memory steer F / L / R', (f.action.value || [0, 0, 0]).map((v) => fmtSigned(v, 2)).join(' / ')], ['Steering mode', f.action.steer ?? 'split'], ['Memory weight (cue gate)', `×${fmt(f.action.cue_gate ?? 1, 2)}`], ['Memory hold-course weight (wall gate)', `×${fmt(f.action.wall_gate ?? 1, 2)}`], ['Pain → rest (freeze habituation)', `×${fmt(f.action.freeze ?? 1, 2)}`]]],
    ['Path integration', [['Estimate x, y', `${fmt(a.est_x, 2)}, ${fmt(a.est_y, 2)}`], ['Estimated heading', `${fmt(headingDeg(a.est_heading), 1)}°`], ['Place cell', f.place_id]]],
    ['Senses', [['Vision rays', f.vision.rays.map((r) => r[2]).join(' · ') || '—'], ['Whiskers L / R', f.vision.whiskers.map((w) => (w ? 'touch' : '—')).join(' / ')], ['Pain', fmt(f.vision.pain, 2)]]],
    ['Neuromodulators', MODULATORS.map((m) => [`${m.name} (${m.mod})`, fmt(f.mod[m.mod] ?? 0, 3)])],
    ['Energy', [['ATP', fmt(f.energy.atp, 3)], ['Glycogen', fmt(f.energy.glycogen, 3)], ['Sensory gate', `${f.trn.state} (${fmt(f.trn.gate, 2)})`], ['Microsleep', f.microsleep.active ? `yes, ${f.microsleep.remaining} left` : 'no'], ['Fatigue pacing', f.energy.pacing ? 'resting to recover' : 'no'], ['Replay', f.replay.active ? replayText(f.replay) : 'no']]],
    ['Criticality', [['κ (exponent 1.5)', fmt(f.crit.kappa, 3)], ['Regime (κ band)', f.crit.regime], ['Coupling (σ)', `${fmt(f.crit.coupling, 2)} (${fmt(f.crit.sigma, 2)})`], ['Active cells', f.crit.active], ['Avalanches', f.crit.n], ['Gain from κ (off at defaults)', `×${fmt(f.crit.gain, 3)}`]]],
    ['Working memory', [['Load', f.wm.load], ['Novelty (checksum change)', fmt(f.wm.novelty, 3)]]],
  ];
}
