// The live console: runs a scenario on the server and draws the brain as it
// thinks. One request is in flight at a time; the tick budget accumulates with
// wall-clock time so the chosen speed holds whatever the frame rate.

import { api } from './api.js';
import { ArenaView, buildArenaLegend } from './arena.js';
import { CompassPanel, CriticalityPanel, DecisionPanel, EnergyPanel, ModulatorPanel, frameTableGroups, renderTable } from './brain.js';
import { LineChart } from './charts.js';
import { MODULATORS, onThemeChange } from './theme.js';
import { $, $$, clear, debounce, el, fmt, fmtAny, fmtSigned, store, toast } from './util.js';

const WINDOW = 600; // ticks shown in the time-series charts
const TRAIL = 1200; // positions kept for the arena trail
const SPARK = 240; // ticks in each neuromodulator sparkline
const TELEPORT = 1.5; // metres per tick; a bigger jump is a reset, not motion
const SERIES_KEYS = ['t', 'r', 'da', 'ne', 'ach', 'ht', 'k', 'atp', 'gly', 'ms'];

const TARGET_LABEL = { beacon: 'beacon', foraging: 'food', hazard_field: 'food', hidden_food: 'food', memory_maze: 'goal' };

export class LiveController {
  constructor({ onRecorded }) {
    this.onRecorded = onRecorded;
    this.active = true;
    this.playing = false;
    this.wantPlay = true;
    this.inflight = false;
    this.budget = 0;
    this.speed = 60;
    this.seq = 0;
    this.sid = null;
    this.frame = null;
    this.defaults = {};
    this.paramControls = {};
    this.lastValueAt = 0;
    this.lastHistAt = 0;
    this.lastChartsAt = 0;
    this.rateSamples = [];
    this.statusKey = '';
    this._loop = this._loop.bind(this);
    this._resetBuffers();

    this.arena = new ArenaView($('#arena'), $('#arena-hover'));
    this.decision = new DecisionPanel($('#decision'));
    this.mods = new ModulatorPanel($('#mods'));
    this.energy = new EnergyPanel($('#energy'));
    this.crit = new CriticalityPanel($('#criticality'));
    this.compass = new CompassPanel($('#compass'));
    this.inspector = $('#inspector');
    this.inspectorDetails = this.inspector.closest('details');

    this.charts = {
      mods: new LineChart($('#chart-mods'), {
        title: 'Neuromodulators',
        series: MODULATORS.map((m) => ({ key: m.key, label: `${m.name} (${m.mod})`, short: m.mod, color: m.key })),
        yMin: 0,
        yMax: 1,
      }),
      reward: new LineChart($('#chart-reward'), {
        title: 'Reward',
        sub: '+ food / goal, − pain',
        series: [{ key: 'r', label: 'Reward', color: 'ink-1' }],
        zeroLine: true,
        minSpan: 0.5,
        format: (v) => fmtSigned(v, 3),
      }),
      kappa: new LineChart($('#chart-kappa'), {
        title: 'Criticality κ',
        sub: 'exponent-1.5 estimator; 1 is not the lattice critical point',
        series: [{ key: 'k', label: 'κ', color: 'ink-1' }],
        band: { lo: 0.85, hi: 1.05, label: '0.85–1.05 band' },
        minSpan: 0.4,
        format: (v) => fmt(v, 3),
      }),
      energy: new LineChart($('#chart-energy'), {
        title: 'Energy',
        series: [
          { key: 'atp', label: 'ATP', short: 'ATP', color: 'ink-1' },
          { key: 'gly', label: 'Glycogen (fraction of store)', short: 'Gly', color: 'ink-2', dash: [5, 3] },
        ],
        yMin: 0,
        yMax: 1,
      }),
    };
    $('#window-readout').textContent = String(WINDOW);

    this._bindControls();
    onThemeChange(() => this._redrawAll());
  }

  // ------------------------------------------------------------------ setup

  async init() {
    this.meta = await api('/api/meta');
    const params = new URLSearchParams(window.location.search);
    const ids = this.meta.scenarios.map((s) => s.id);
    let scenario = params.get('scenario') || store.get('quantum-rat-scenario') || 'foraging';
    if (!ids.includes(scenario)) scenario = 'foraging';
    const seed = Number.parseInt(params.get('seed') ?? '', 10);
    const speed = Number.parseInt(params.get('speed') ?? '', 10);
    if (Number.isFinite(speed) && speed > 0) this._setSpeed(speed);
    if (params.get('paused') === '1') this.wantPlay = false;
    this._buildScenarioList();
    await this.start(scenario, Number.isFinite(seed) ? seed : this.meta.default_seed);
  }

  _buildScenarioList() {
    const list = clear($('#scenario-list'));
    for (const s of this.meta.scenarios) {
      list.append(
        el(
          'button',
          {
            class: 'scenario',
            type: 'button',
            role: 'radio',
            'aria-checked': 'false',
            dataset: { id: s.id },
            onclick: () => this.start(s.id, this.seed ?? this.meta.default_seed),
          },
          el('span', { class: 'scenario-title', text: s.title }),
          el('span', { class: 'scenario-summary', text: s.summary }),
        ),
      );
    }
  }

  _bindControls() {
    $('#btn-play').addEventListener('click', () => (this.playing ? this.pause() : this.play()));
    $('#btn-step').addEventListener('click', () => {
      this.pause();
      this._step(1);
    });
    $('#btn-reset').addEventListener('click', () => this.reset(this.seed));
    $('#btn-dice').addEventListener('click', () => this.reset(Math.floor(Math.random() * 100000)));
    $('#seed').addEventListener('change', (e) => {
      const v = Number.parseInt(e.target.value, 10);
      if (Number.isFinite(v) && v >= 0) this.reset(v);
    });
    $('#speed').addEventListener('change', (e) => this._setSpeed(Number(e.target.value)));
    $('#btn-record').addEventListener('click', () => this.record());
    $('#events-clear').addEventListener('click', () => clear($('#event-log')));
    $('#params-reset').addEventListener('click', () => this._resetAllParams());
    for (const box of $$('[data-layer]')) box.addEventListener('change', () => this.arena.setLayer(box.dataset.layer, box.checked));
    this.inspectorDetails.addEventListener('toggle', () => this._renderInspector());

    document.addEventListener('keydown', (e) => {
      if (!this.active || e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.target.closest('input, select, textarea, button, summary, [contenteditable]')) return;
      if (e.code === 'Space') {
        e.preventDefault();
        this.playing ? this.pause() : this.play();
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        this.pause();
        this._step(1);
      }
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) this._suspend();
      else this._resume();
    });
  }

  _setSpeed(speed) {
    this.speed = speed;
    const select = $('#speed');
    if (![...select.options].some((o) => Number(o.value) === speed)) select.append(el('option', { value: speed, text: `${speed} ticks/s` }));
    select.value = String(speed);
  }

  // -------------------------------------------------------------- sessions

  async start(scenarioId, seed) {
    const old = this.sid;
    this.sid = null;
    this._stopLoop();
    if (old) api(`/api/sim/${old}`, { method: 'DELETE' }).catch(() => {});
    try {
      const payload = await api('/api/sim', { method: 'POST', body: { scenario: scenarioId, seed } });
      store.set('quantum-rat-scenario', scenarioId);
      this.defaults = Object.fromEntries(payload.params.map((p) => [p.key, p.value]));
      this._load(payload, { fresh: true });
    } catch (err) {
      this._error(err);
    }
  }

  async reset(seed) {
    if (!this.sid) return;
    const sid = this.sid;
    this._stopLoop();
    try {
      const payload = await api(`/api/sim/${sid}/reset`, { method: 'POST', body: { seed } });
      if (sid !== this.sid) return;
      this._load(payload, { fresh: false });
    } catch (err) {
      this._error(err);
    }
  }

  _load(payload, { fresh }) {
    this.sid = payload.id;
    this.seed = payload.seed;
    this.scenario = payload.scenario;
    this.seq = 0;
    this._resetBuffers();
    $('#seed').value = String(payload.seed);
    for (const card of $$('.scenario')) card.setAttribute('aria-checked', String(card.dataset.id === payload.scenario.id));
    clear($('#scenario-watch')).append(...payload.scenario.watch.map((w) => el('li', { text: w })));
    this._buildActions(payload.scenario.actions);
    if (fresh) this._buildParams(payload.params);
    else this._syncParams(payload.params);
    clear($('#event-log'));
    this._events(payload.events);
    this.frame = payload.frame;
    this._pushTrail(payload.frame.agent.x, payload.frame.agent.y);
    this.arena.set({ trail: this.trail, valueMap: payload.value_map, targetLabel: TARGET_LABEL[payload.scenario.id] || 'target' });
    this.crit.setHistogram(payload.histogram);
    this.legendKinds = '';
    this.statusKey = '';
    this._render(true);
    if (this.wantPlay) this.play();
    else this._syncPlayButton();
  }

  _resetBuffers() {
    this.buf = Object.fromEntries(SERIES_KEYS.map((k) => [k, []]));
    this.trail = [];
  }

  // ------------------------------------------------------------ transport

  play() {
    this.wantPlay = true;
    if (!this.sid || !this.active || document.hidden) {
      this._syncPlayButton();
      return;
    }
    if (!this.playing) {
      this.playing = true;
      this.lastFrame = performance.now();
      this.budget = 0;
      requestAnimationFrame(this._loop);
    }
    this._syncPlayButton();
  }

  pause() {
    this.wantPlay = false;
    this._stopLoop();
  }

  _stopLoop() {
    this.playing = false;
    this._syncPlayButton();
  }

  _suspend() {
    const want = this.wantPlay;
    this._stopLoop();
    this.wantPlay = want;
  }

  _resume() {
    if (this.wantPlay) this.play();
  }

  setActive(active) {
    this.active = active;
    if (active) {
      this._resume();
      this._redrawAll();
    } else this._suspend();
  }

  _syncPlayButton() {
    const btn = $('#btn-play');
    btn.dataset.playing = String(this.playing);
    btn.querySelector('.btn-label').textContent = this.playing ? 'Pause' : 'Play';
    btn.setAttribute('aria-pressed', String(this.playing));
  }

  _loop(now) {
    if (!this.playing) return;
    requestAnimationFrame(this._loop);
    const dt = Math.min(0.25, (now - this.lastFrame) / 1000);
    this.lastFrame = now;
    this.budget = Math.min(this.budget + dt * this.speed, this.speed * 0.25 + 1);
    if (this.inflight || this.budget < 1) return;
    const n = Math.min(this.meta.max_steps, Math.floor(this.budget));
    this.budget -= n;
    this._step(n);
  }

  async _step(n) {
    if (!this.sid || this.inflight) return;
    const sid = this.sid;
    this.inflight = true;
    const now = performance.now();
    const wantValue = now - this.lastValueAt > 400;
    const wantHist = now - this.lastHistAt > 1000;
    try {
      const res = await api(`/api/sim/${sid}/step`, {
        method: 'POST',
        body: { n, since: this.seq, value_map: wantValue, histogram: wantHist },
      });
      if (sid !== this.sid) return;
      this._ingest(res.series);
      this._events(res.events);
      this.frame = res.frame;
      if (res.value_map) {
        this.lastValueAt = now;
        this.arena.set({ valueMap: res.value_map });
      }
      if (res.histogram) {
        this.lastHistAt = now;
        this.crit.setHistogram(res.histogram);
      }
      this._measureRate(res.series.length);
      this._render(!this.playing);
    } catch (err) {
      this._error(err);
    } finally {
      this.inflight = false;
    }
  }

  _ingest(series) {
    for (const p of series) {
      for (const k of SERIES_KEYS) this.buf[k].push(p[k]);
      this._pushTrail(p.x, p.y);
    }
    const extra = this.buf.t.length - WINDOW;
    if (extra > 100) for (const k of SERIES_KEYS) this.buf[k].splice(0, extra);
    const trailExtra = this.trail.length - TRAIL;
    if (trailExtra > 100) this.trail.splice(0, trailExtra);
  }

  _pushTrail(x, y) {
    const last = this.trail[this.trail.length - 1];
    if (last && Math.hypot(last[0] - x, last[1] - y) > TELEPORT) this.trail.push(null);
    this.trail.push([x, y]);
  }

  _measureRate(n) {
    const now = performance.now();
    this.rateSamples.push([now, n]);
    while (this.rateSamples.length && now - this.rateSamples[0][0] > 1500) this.rateSamples.shift();
    if (this.rateSamples.length < 2) return;
    const span = (now - this.rateSamples[0][0]) / 1000;
    const total = this.rateSamples.slice(1).reduce((s, [, k]) => s + k, 0);
    $('#rate-readout').textContent = this.playing && span > 0.2 ? `${Math.round(total / span)}/s` : '—';
  }

  async record() {
    if (!this.sid) return;
    try {
      const res = await api(`/api/sim/${this.sid}/record`, { method: 'POST', body: { since: this.seq } });
      this._events(res.events);
      toast(`Saved as run “${res.run_id}”.`, { action: { label: 'Open in Replay', onClick: () => this.onRecorded(res.run_id) }, ms: 8000 });
    } catch (err) {
      this._error(err);
    }
  }

  _error(err) {
    if (err.status === 404 && this.scenario) {
      toast('That simulation expired on the server, so a fresh one was started.', { level: 'critical' });
      this.start(this.scenario.id, this.seed);
      return;
    }
    if (err.status === 0) {
      this._suspend();
      toast(err.message, { level: 'critical', action: { label: 'Retry', onClick: () => this.play() }, ms: 15000 });
      return;
    }
    toast(err.message, { level: 'critical' });
  }

  // ------------------------------------------------------------- events

  _events(events) {
    if (!events || !events.length) return;
    const log = $('#event-log');
    const icons = { good: '✓', warning: '!', critical: '✕', info: '•' };
    for (const e of events) {
      if (e.seq <= this.seq) continue;
      this.seq = e.seq;
      log.prepend(
        el(
          'li',
          { class: 'event', dataset: { level: e.level || 'info', kind: e.kind || '' } },
          el('span', { class: 'event-icon', 'aria-hidden': 'true', text: icons[e.level] || '•' }),
          el('span', { class: 'event-tick', text: `t ${e.tick}` }),
          el('span', { class: 'event-text', text: e.text }),
        ),
      );
    }
    while (log.children.length > 200) log.lastElementChild.remove();
  }

  // ---------------------------------------------------- scenario actions

  _buildActions(actions) {
    const host = clear($('#scenario-actions'));
    for (const a of actions || []) {
      host.append(
        el('button', { class: 'btn', type: 'button', text: a.label, title: a.help, onclick: () => this._action(a.id) }),
        el('p', { class: 'action-help', text: a.help }),
      );
    }
  }

  async _action(actionId) {
    if (!this.sid) return;
    try {
      const res = await api(`/api/sim/${this.sid}/action`, { method: 'POST', body: { action: actionId, since: this.seq } });
      this._events(res.events);
      this.frame = res.frame;
      this.arena.set({ valueMap: res.value_map });
      this._render(true);
    } catch (err) {
      this._error(err);
    }
  }

  // ------------------------------------------------------------ parameters

  _buildParams(params) {
    const host = clear($('#params'));
    this.paramControls = {};
    const groups = new Map();
    for (const p of params) {
      if (!groups.has(p.group)) groups.set(p.group, []);
      groups.get(p.group).push(p);
    }
    for (const [group, items] of groups) {
      const details = el('details', { class: 'param-group', open: true }, el('summary', { text: group }));
      for (const p of items) details.append(this._paramRow(p));
      host.append(details);
    }
  }

  _paramRow(p) {
    const id = `param-${p.key.replace(/\W/g, '-')}`;
    const value = el('span', { class: 'param-value' });
    const range = el('input', { id, type: 'range', min: p.min, max: p.max, step: p.step, value: p.value, 'aria-describedby': `${id}-help` });
    const reset = el('button', { class: 'param-reset', type: 'button', title: 'Back to the scenario default', 'aria-label': `Reset ${p.label}`, text: '↺' });
    const send = debounce((v) => this._sendParam(p.key, v), 120);
    range.addEventListener('input', () => {
      this._showParam(p.key, Number(range.value));
      send(Number(range.value));
    });
    reset.addEventListener('click', () => {
      const d = this.defaults[p.key];
      range.value = String(d);
      this._showParam(p.key, d);
      send.flush(d);
    });
    this.paramControls[p.key] = { p, range, value, reset };
    this._showParam(p.key, p.value);
    return el(
      'div',
      { class: 'param' },
      el('div', { class: 'param-head' }, el('label', { for: id, text: p.label }), value, reset),
      range,
      el('div', { class: 'param-help', id: `${id}-help`, text: p.help }),
    );
  }

  _showParam(key, v) {
    const c = this.paramControls[key];
    if (!c) return;
    const digits = c.p.integer ? 0 : c.p.step < 0.01 ? 3 : c.p.step < 0.1 ? 2 : 1;
    c.value.textContent = fmt(v, digits);
    const changed = Math.abs(v - this.defaults[key]) > 1e-9;
    c.value.dataset.changed = String(changed);
    c.reset.disabled = !changed;
  }

  _syncParams(params) {
    for (const p of params) {
      const c = this.paramControls[p.key];
      if (!c) continue;
      c.range.value = String(p.value);
      this._showParam(p.key, p.value);
    }
  }

  async _sendParam(key, value) {
    if (!this.sid) return;
    try {
      const res = await api(`/api/sim/${this.sid}/param`, { method: 'POST', body: { key, value, since: this.seq } });
      this._events(res.events);
      this._syncParams(res.params);
      this.frame = res.frame;
      if (key === 'criticality.coupling') this.lastHistAt = 0;
      this._render(true);
    } catch (err) {
      this._error(err);
    }
  }

  async _resetAllParams() {
    for (const [key, c] of Object.entries(this.paramControls)) {
      if (!c.reset.disabled) {
        c.range.value = String(this.defaults[key]);
        await this._sendParam(key, this.defaults[key]);
      }
    }
  }

  // -------------------------------------------------------------- render

  _render(force = false) {
    const f = this.frame;
    if (!f) return;
    $('#tick-readout').textContent = String(f.tick);

    const kinds = new Set(f.world.objects.map((o) => o.kind));
    if (this.scenario && (this.scenario.id === 'memory_maze' || this.scenario.id === 'hidden_food')) kinds.add('hidden');
    const kindKey = [...kinds].sort().join(',');
    if (kindKey !== this.legendKinds) {
      this.legendKinds = kindKey;
      buildArenaLegend($('#arena-legend'), { kinds, targetLabel: TARGET_LABEL[this.scenario?.id] || 'target', value: true, rays: true, estimate: true });
    }
    this.arena.set({
      bounds: f.world.bounds,
      objects: f.world.objects,
      painZone: f.world.pain_zone,
      agent: { x: f.agent.x, y: f.agent.y, heading: f.agent.heading },
      estimate: { x: f.agent.est_x, y: f.agent.est_y, heading: f.agent.est_heading },
      rays: f.vision.rays,
      range: f.vision.range,
      fov: f.vision.fov,
      whiskers: f.vision.whiskers,
      pain: f.vision.pain,
      replayCell: f.replay.cell,
      goalCell: f.goal ?? null,
      microsleep: f.microsleep.active,
      trail: this.trail,
    });

    this.decision.update(f.action);
    const spark = Object.fromEntries(MODULATORS.map((m) => [m.key, this.buf[m.key].slice(-SPARK)]));
    this.mods.update(f.mod, spark);
    this.energy.update(f);
    this.crit.update(f.crit);
    this.compass.update(f.agent, f.place_id);
    this._renderStatus(f.status);
    this._renderInspector();

    const now = performance.now();
    if (force || now - this.lastChartsAt > 66) {
      this.lastChartsAt = now;
      this._renderCharts();
    }
  }

  _renderCharts() {
    const b = this.buf;
    const n = b.t.length;
    const from = Math.max(0, n - WINDOW);
    const sl = (k) => b[k].slice(from);
    const xs = sl('t');
    const shade = sl('ms');
    this.charts.mods.setData(xs, Object.fromEntries(MODULATORS.map((m) => [m.key, sl(m.key)])), shade);
    this.charts.reward.setData(xs, { r: sl('r') }, shade);
    this.charts.kappa.setData(xs, { k: sl('k') }, shade);
    const store = this.frame?.energy.glycogen_max || 3;
    this.charts.energy.setData(xs, { atp: sl('atp'), gly: sl('gly').map((g) => g / store) }, shade);
  }

  _renderInspector() {
    if (!this.frame || !this.inspectorDetails.open) return;
    renderTable(this.inspector, frameTableGroups(this.frame));
  }

  _renderStatus(status) {
    const key = JSON.stringify(status);
    if (key === this.statusKey) return;
    this.statusKey = key;
    const dl = clear($('#scenario-status'));
    dl.append(el('dt', { text: 'Seed' }), el('dd', { text: String(this.seed) }));
    for (const [k, v] of Object.entries(status)) {
      if (k === 'trials') continue;
      dl.append(el('dt', { text: k }), el('dd', { text: fmtAny(v) }));
    }
    this._renderTrials(status.trials);
  }

  _renderTrials(trials) {
    const host = $('#trial-chart');
    if (!Array.isArray(trials)) {
      host.hidden = true;
      return;
    }
    host.hidden = false;
    clear(host);
    const max = Math.max(10, ...trials.map((t) => t.ticks));
    const bars = el('div', { class: 'trial-bars', role: 'img', 'aria-label': 'Ticks taken to reach the goal on each trial' });
    const marks = el('div', { class: 'trial-marks', 'aria-hidden': 'true' });
    const every = trials.length > 12 ? 5 : 1;
    for (const t of trials) {
      const bar = el('div', {
        class: 'trial-bar',
        dataset: { visible: String(t.visible), reached: String(t.reached) },
        title: `Trial ${t.trial}: ${t.visible ? 'visible goal (training)' : 'hidden goal (recall)'}, ${t.reached ? `reached in ${t.ticks} ticks` : `timed out after ${t.ticks} ticks`}`,
      });
      bar.style.height = `${Math.max(4, (100 * t.ticks) / max)}%`;
      bars.append(bar);
      marks.append(el('span', { text: t.trial % every === 0 || t.trial === 1 ? String(t.trial) : '' }));
    }
    const first = trials.length ? trials[0].trial : 1;
    host.append(
      el('div', { class: 'tc-title' }, el('span', { text: 'Ticks to reach the goal' }), el('span', { class: 'num', text: `tallest = ${max}` })),
      trials.length ? bars : el('div', { class: 'event-empty', text: 'No trials finished yet.' }),
      trials.length ? marks : null,
      el(
        'div',
        { class: 'trial-key' },
        el('span', {}, el('span', { class: 'sw sw-train' }), 'visible (training)'),
        el('span', {}, el('span', { class: 'sw sw-recall' }), 'hidden (recall)'),
        el('span', {}, el('span', { class: 'sw sw-fail' }), 'timed out'),
        first > 1 ? el('span', { text: `showing trials ${first}–${trials[trials.length - 1].trial}` }) : null,
      ),
    );
  }

  _redrawAll() {
    this.legendKinds = '';
    this.statusKey = '';
    this.arena.render();
    this.crit.redraw();
    this.compass.redraw();
    this._render(true);
    for (const c of Object.values(this.charts)) c.render();
  }
}
