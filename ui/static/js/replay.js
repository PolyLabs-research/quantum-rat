// Replay viewer: open a recorded run, scrub or play through it, see the path in
// the arena (with the scene when the run saved one), the signals over the whole
// run, key moments, and every logged field of the selected tick.

import { api } from './api.js';
import { ArenaView, buildArenaLegend } from './arena.js';
import { renderTable } from './brain.js';
import { LineChart } from './charts.js';
import { MODULATORS, onThemeChange } from './theme.js';
import { $, $$, clear, debounce, el, fmt, fmtAny, fmtSigned, headingDeg, toast } from './util.js';

const TELEPORT = 1.5;
const MAX_MOMENTS = 300;
const SUMMARY_FIRST = ['protocol', 'source', 'seed', 'ticks_run', 'ticks_requested', 'score', 'schema_version'];

export class ReplayController {
  constructor() {
    this.active = false;
    this.loaded = false;
    this.playing = false;
    this.index = 0;
    this.cols = null;
    this.episode = null;
    this._loop = this._loop.bind(this);

    this.arena = new ArenaView($('#rp-arena'), $('#rp-arena-hover'));
    const seek = (i) => this.seek(i);
    this.charts = {
      mods: new LineChart($('#rp-chart-mods'), {
        title: 'Neuromodulators',
        series: MODULATORS.map((m) => ({ key: m.key, label: `${m.name} (${m.mod})`, short: m.mod, color: m.key })),
        yMin: 0,
        yMax: 1,
        onSeek: seek,
      }),
      reward: new LineChart($('#rp-chart-reward'), {
        title: 'Reward',
        series: [{ key: 'r', label: 'Reward', color: 'ink-1' }],
        zeroLine: true,
        minSpan: 0.5,
        format: (v) => fmtSigned(v, 3),
        onSeek: seek,
      }),
      kappa: new LineChart($('#rp-chart-kappa'), {
        title: 'Criticality κ',
        sub: '1 = critical',
        series: [{ key: 'k', label: 'κ', color: 'ink-1' }],
        band: { lo: 0.85, hi: 1.05, label: 'near-critical' },
        minSpan: 0.4,
        format: (v) => fmt(v, 3),
        onSeek: seek,
      }),
      energy: new LineChart($('#rp-chart-energy'), {
        title: 'Energy',
        series: [
          { key: 'atp', label: 'ATP', short: 'ATP', color: 'ink-1' },
          { key: 'gly', label: 'Glycogen (fraction of store)', short: 'Gly', color: 'ink-2', dash: [5, 3] },
        ],
        yMin: 0,
        yMax: 1,
        onSeek: seek,
      }),
    };

    this._fetchTick = debounce((i) => this._loadTick(i), 120);
    this._bind();
    onThemeChange(() => this._redraw());
  }

  _bind() {
    $('#runs-refresh').addEventListener('click', () => this.refreshRuns($('#run-select').value));
    $('#run-select').addEventListener('change', (e) => this._loadRun(e.target.value));
    $('#episode-select').addEventListener('change', (e) => this._loadEpisode(this.episodes[Number(e.target.value)]));
    $('#rp-play').addEventListener('click', () => (this.playing ? this.pause() : this.play()));
    $('#rp-scrub').addEventListener('input', (e) => {
      this.pause();
      this.seek(Number(e.target.value));
    });
    for (const box of $$('[data-rp-layer]')) box.addEventListener('change', () => this.arena.setLayer(box.dataset.rpLayer, box.checked));
    document.addEventListener('keydown', (e) => {
      if (!this.active || !this.cols || e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.target.closest('input, select, textarea, button, summary')) return;
      if (e.code === 'Space') {
        e.preventDefault();
        this.playing ? this.pause() : this.play();
      } else if (e.code === 'ArrowRight' || e.code === 'ArrowLeft') {
        e.preventDefault();
        this.pause();
        this.seek(this.index + (e.code === 'ArrowRight' ? 1 : -1));
      }
    });
  }

  setActive(active) {
    this.active = active;
    if (!active) this.pause();
    else if (!this.loaded) this.refreshRuns();
    else this._redraw();
  }

  // ----------------------------------------------------------------- runs

  async refreshRuns(selectId) {
    this.loaded = true;
    let data;
    try {
      data = await api('/api/runs');
    } catch (err) {
      toast(err.message, { level: 'critical' });
      return;
    }
    const select = clear($('#run-select'));
    $('#runs-root').replaceChildren('Reading runs from ', el('code', { text: data.root || 'runs' }));
    const runs = data.runs || [];
    for (const r of runs) {
      const bits = [r.id];
      if (r.type === 'tournament') bits.push('· tournament');
      else if (r.ticks_run) bits.push(`· ${r.ticks_run} ticks`);
      select.append(el('option', { value: r.id, text: bits.join(' ') }));
    }
    this._showEmpty(!runs.length);
    if (!runs.length) {
      clear($('#episode-select'));
      return;
    }
    const pick = runs.some((r) => r.id === selectId) ? selectId : runs[0].id;
    select.value = pick;
    await this._loadRun(pick);
  }

  async openRun(runId) {
    await this.refreshRuns(runId);
  }

  _showEmpty(empty) {
    const box = $('#replay-empty');
    box.hidden = !empty;
    if (!empty) return;
    clear(box).append(
      el('h2', { text: 'No recorded runs yet' }),
      el('p', {}, 'In the Live tab, press ', el('strong', { text: 'Record to replay' }), ' to save a session here.'),
      el('p', {}, 'Or record a headless run from the command line, then press Refresh:'),
      el('p', {}, el('code', { text: 'python -m experiments.runner --protocol foraging --ticks 2000' })),
    );
  }

  async _loadRun(runId) {
    this.pause();
    try {
      const data = await api(`/api/runs/${encodeURIComponent(runId)}/episodes`);
      this.runId = runId;
      this.episodes = data.episodes || [];
      const select = clear($('#episode-select'));
      this.episodes.forEach((ep, i) => {
        const label = ep.agent_id === 'default' ? 'Whole run' : `${ep.agent_id} / ${ep.protocol}${ep.has_ticks === false ? ' (summary only)' : ''}`;
        select.append(el('option', { value: i, text: label }));
      });
      const first = Math.max(0, this.episodes.findIndex((ep) => ep.has_ticks !== false));
      select.value = String(first);
      select.disabled = this.episodes.length < 2;
      if (this.episodes.length) await this._loadEpisode(this.episodes[first]);
    } catch (err) {
      toast(err.message, { level: 'critical' });
    }
  }

  _base(ep) {
    return `/api/runs/${encodeURIComponent(this.runId)}/${encodeURIComponent(ep.agent_id)}/${encodeURIComponent(ep.protocol)}`;
  }

  async _loadEpisode(ep) {
    if (!ep) return;
    this.pause();
    this.episode = ep;
    const base = this._base(ep);
    const [summary, scene, series] = await Promise.all([
      api(`${base}/summary`).catch(() => null),
      api(`${base}/scene`).catch(() => null),
      api(`${base}/series`).catch((err) => ({ error: err.message })),
    ]);
    if (ep !== this.episode) return;
    this._renderSummary(summary);
    this.scene = scene;
    if (!series || series.error || !series.columns || !series.columns.t.length) {
      this.cols = null;
      this._clearPlayback(series && series.error ? 'This episode has no tick log to replay (tournaments need --include-ticks).' : 'This run is empty.');
      return;
    }
    this.cols = series.columns;
    this.stride = series.stride;
    this.total = series.total;
    this._prepare();
    this.seek(0);
  }

  _clearPlayback(message) {
    $('#rp-scrub').max = '0';
    $('#rp-tick').textContent = '—';
    clear($('#moments')).append(el('li', { class: 'event-empty', text: message }));
    clear($('#rp-inspector'));
    this.arena.set({ objects: [], path: null, trail: [], agent: null, estimate: null });
    for (const c of Object.values(this.charts)) c.setData([], {});
  }

  // ------------------------------------------------------------- prepare

  _prepare() {
    const c = this.cols;
    const n = c.t.length;
    const scene = this.scene;
    // Bounds: the scene's, else big enough for the path.
    let bounds = scene?.bounds;
    if (!bounds) {
      const reach = Math.max(10, ...c.x.map(Math.abs), ...c.y.map(Math.abs));
      bounds = [Math.ceil(reach), Math.ceil(reach)];
    }
    // Path with breaks at teleports (trial resets).
    this.path = [];
    for (let i = 0; i < n; i++) {
      if (i && Math.hypot(c.x[i] - c.x[i - 1], c.y[i] - c.y[i - 1]) > TELEPORT * this.stride) this.path.push(null);
      this.path.push([c.x[i], c.y[i]]);
    }
    // Heading from motion (the body heading is not logged), held while still.
    this.heading = new Array(n);
    const start = scene?.start_pose;
    let h = start ? start[2] + c.hd[0] : 0;
    for (let i = 0; i < n; i++) {
      const j = i + 1 < n ? i + 1 : i;
      const k = j === i ? i - 1 : i;
      if (k >= 0) {
        const dx = c.x[j] - c.x[k];
        const dy = c.y[j] - c.y[k];
        const d = Math.hypot(dx, dy);
        if (d > 1e-3 && d < TELEPORT * this.stride) h = Math.atan2(dy, dx);
      }
      this.heading[i] = h;
    }
    // Key moments.
    this.moments = [];
    const push = (i, level, text) => this.moments.length < MAX_MOMENTS && this.moments.push({ i, level, text });
    for (let i = 1; i < n; i++) {
      if (c.r[i] > 0.3 && c.r[i - 1] <= 0.3) push(i, 'good', `Reward ${fmtSigned(c.r[i], 2)}`);
      if (c.pain[i] > 0.5 && c.pain[i - 1] <= 0.5) push(i, 'critical', 'Entered a pain zone');
      if (c.ms[i] && !c.ms[i - 1]) push(i, 'warning', 'Microsleep: ATP low, senses gated, replay');
      if (c.trn[i] === 'NARROW' && c.trn[i - 1] === 'OPEN') push(i, 'warning', 'Sensory gate narrowed (tired)');
      if (Math.hypot(c.x[i] - c.x[i - 1], c.y[i] - c.y[i - 1]) > TELEPORT * this.stride) push(i, 'info', 'Back to the start (new trial)');
    }
    this._renderMoments();

    const kinds = new Set((scene?.objects || []).map((o) => o.kind));
    const targetLabel = { beacon: 'beacon', foraging: 'food', hazard_field: 'food', hidden_food: 'food', memory_maze: 'goal' }[scene?.scenario?.id || scene?.protocol] || 'target';
    this.arena.set({
      bounds,
      objects: scene?.objects || [],
      painZone: 1.5,
      path: this.path,
      valueMap: null,
      rays: [],
      targetLabel,
      layers: { ...this.arena.s.layers, rays: false, value: false },
    });
    buildArenaLegend($('#rp-legend'), { kinds, targetLabel, value: false, rays: false, estimate: Boolean(start), path: true });
    if (!scene) $('#rp-legend').append(el('span', { class: 'legend-item', text: 'No scene.json in this run, so objects are not shown.' }));

    $('#rp-scrub').max = String(n - 1);
    const xs = c.t;
    const shade = c.ms;
    this.charts.mods.setData(xs, Object.fromEntries(MODULATORS.map((m) => [m.key, c[m.key]])), shade);
    this.charts.reward.setData(xs, { r: c.r }, shade);
    this.charts.kappa.setData(xs, { k: c.k }, shade);
    const store = scene?.energy?.glycogen_max || 3;
    this.charts.energy.setData(xs, { atp: c.atp, gly: c.gly.map((g) => g / store) }, shade);
  }

  _renderMoments() {
    const list = clear($('#moments'));
    if (!this.moments.length) {
      list.append(el('li', { class: 'event-empty', text: 'Nothing notable: no rewards, pain, microsleeps or trial resets.' }));
      return;
    }
    const icons = { good: '✓', warning: '!', critical: '✕', info: '•' };
    for (const m of this.moments) {
      list.append(
        el(
          'li',
          {},
          el(
            'button',
            { class: 'event', type: 'button', dataset: { level: m.level }, onclick: () => this.seek(m.i) },
            el('span', { class: 'event-icon', 'aria-hidden': 'true', text: icons[m.level] }),
            el('span', { class: 'event-tick', text: `t ${this.cols.t[m.i]}` }),
            el('span', { class: 'event-text', text: m.text }),
          ),
        ),
      );
    }
  }

  _renderSummary(summary) {
    const host = clear($('#summary'));
    if (!summary) {
      host.append(el('p', { class: 'hint', text: 'No summary.json for this episode.' }));
      return;
    }
    const keys = Object.keys(summary);
    const ordered = [...SUMMARY_FIRST.filter((k) => k in summary), ...keys.filter((k) => !SUMMARY_FIRST.includes(k)).sort()];
    const dl = el('dl', { class: 'summary-kv' });
    let nested = false;
    for (const k of ordered) {
      const v = summary[k];
      if (v !== null && typeof v === 'object') {
        nested = true;
        continue;
      }
      const text = typeof v === 'string' && v.length > 24 ? `${v.slice(0, 12)}…${v.slice(-6)}` : fmtAny(v);
      dl.append(el('dt', { text: k.replace(/_/g, ' ') }), el('dd', { text, title: String(v) }));
    }
    host.append(dl);
    if (nested) {
      host.append(el('details', { class: 'summary-more' }, el('summary', { text: 'Full summary (JSON)' }), el('pre', { text: JSON.stringify(summary, null, 2) })));
    }
  }

  // ------------------------------------------------------------- playback

  seek(i) {
    if (!this.cols) return;
    const n = this.cols.t.length;
    this.index = Math.max(0, Math.min(n - 1, Math.round(i)));
    this._drawCursor();
    this._fetchTick(this.index);
  }

  _drawCursor() {
    const c = this.cols;
    const i = this.index;
    const start = this.scene?.start_pose;
    let estimate = null;
    if (start) {
      const [sx, sy, sh] = start;
      const cs = Math.cos(sh);
      const sn = Math.sin(sh);
      estimate = { x: sx + cs * c.gx[i] - sn * c.gy[i], y: sy + sn * c.gx[i] + cs * c.gy[i], heading: sh + c.hd[i] };
    }
    // Trail since the last trial reset (at most the last 600 samples).
    const from = Math.max(0, i + 1 - 600);
    const trail = [];
    for (let j = from; j <= i; j++) {
      if (j > from && Math.hypot(c.x[j] - c.x[j - 1], c.y[j] - c.y[j - 1]) > TELEPORT * this.stride) trail.length = 0;
      trail.push([c.x[j], c.y[j]]);
    }
    this.arena.set({
      agent: { x: c.x[i], y: c.y[i], heading: this.heading[i] },
      estimate,
      trail,
      pain: c.pain[i],
      microsleep: Boolean(c.ms[i]),
    });
    $('#rp-scrub').value = String(i);
    $('#rp-tick').textContent = `${c.t[i]} / ${c.t[c.t.length - 1]}`;
    for (const chart of Object.values(this.charts)) chart.setCursor(c.t[i]);
  }

  async _loadTick(i) {
    if (!this.cols || !this.episode) return;
    const ep = this.episode;
    try {
      const data = await api(`${this._base(ep)}/ticks?start=${i * this.stride}&limit=1`);
      if (ep !== this.episode || i !== this.index) return;
      const row = data.ticks[0];
      if (row) renderTable($('#rp-inspector'), tickGroups(row, this.heading[i]));
    } catch {
      /* inspector is best-effort */
    }
  }

  play() {
    if (!this.cols) return;
    if (this.index >= this.cols.t.length - 1) this.seek(0);
    this.playing = true;
    this.acc = 0;
    this.lastFrame = performance.now();
    this._syncButton();
    requestAnimationFrame(this._loop);
  }

  pause() {
    this.playing = false;
    this._syncButton();
  }

  _syncButton() {
    const btn = $('#rp-play');
    btn.dataset.playing = String(this.playing);
    btn.querySelector('.btn-label').textContent = this.playing ? 'Pause' : 'Play';
    btn.setAttribute('aria-pressed', String(this.playing));
  }

  _loop(now) {
    if (!this.playing || !this.cols) return;
    const dt = Math.min(0.25, (now - this.lastFrame) / 1000);
    this.lastFrame = now;
    this.acc += (dt * Number($('#rp-speed').value)) / this.stride;
    const adv = Math.floor(this.acc);
    if (adv >= 1) {
      this.acc -= adv;
      const last = this.cols.t.length - 1;
      this.index = Math.min(last, this.index + adv);
      this._drawCursor();
      this._fetchTick(this.index);
      if (this.index >= last) {
        this.pause();
        return;
      }
    }
    requestAnimationFrame(this._loop);
  }

  _redraw() {
    if (!this.cols) return;
    this._prepare();
    this._drawCursor();
  }
}

function tickGroups(row, heading) {
  const mods = row.neuromodulators || {};
  const used = new Set();
  const take = (k) => {
    used.add(k);
    return row[k];
  };
  const pos = take('pos') || [0, 0];
  const groups = [
    ['Body', [['Tick', take('tick')], ['x, y (m)', `${fmt(pos[0], 2)}, ${fmt(pos[1], 2)}`], ['Heading (from motion)', `${fmt(headingDeg(heading), 0)}°`], ['Action', take('action_name')], ['Thrust, turn', `${fmt(take('action_thrust'), 3)}, ${fmt(take('action_turn'), 3)}`], ['Reward', fmtSigned(take('reward'), 3)]]],
    ['Path integration', [['Grid x, y', `${fmt(take('grid_x'), 2)}, ${fmt(take('grid_y'), 2)}`], ['HD angle', `${fmt(headingDeg(take('hd_angle')), 1)}°`], ['Place cell', take('place_id')]]],
    ['Senses', [['Pain', fmt(take('obs_pain'), 3)], ['Forward Δ', fmt(take('obs_forward_delta'), 3)], ['Turn Δ', fmt(take('obs_turn_delta'), 3)], ['Checksum', String(take('obs_checksum') || '—').slice(0, 12)]]],
    ['Neuromodulators', MODULATORS.map((m) => [`${m.name} (${m.mod})`, fmt(mods[m.mod] ?? 0, 3)])],
    ['Energy & gate', [['ATP', fmt(take('atp'), 3)], ['Glycogen', fmt(take('glycogen'), 3)], ['Sensory gate', take('trn_state')], ['Microsleep', take('microsleep_active') ? `yes, ${take('microsleep_ticks_remaining')} left` : 'no'], ['Replay', take('replay_active') ? `step ${take('replay_index')}` : 'no']]],
    ['Criticality', [['κ', fmt(take('kappa'), 3)], ['Avalanche completed', take('avalanche_size')], ['Active cells', take('criticality_active')]]],
    ['Working memory', [['Load', take('wm_load')], ['Novelty (checksum change)', fmt(take('wm_novelty'), 3)]]],
  ];
  for (const k of ['neuromodulators', 'microsleep_ticks_remaining', 'replay_index']) used.add(k);
  const rest = Object.keys(row)
    .filter((k) => !used.has(k))
    .map((k) => [k.replace(/_/g, ' '), fmtAny(row[k])]);
  if (rest.length) groups.push(['Other fields', rest]);
  return groups;
}
