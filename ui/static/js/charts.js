// Canvas charts: a time-series line chart with a crosshair tooltip, sparklines,
// the log-log avalanche-size histogram and the kappa gauge.
//
// Conventions: one y-axis per chart, 2px lines, hairline grid, labels in ink
// (never in the series colour; a coloured mark beside the text carries
// identity), a legend plus direct end-labels when a chart has 2+ series.

import { T } from './theme.js';
import { alpha, clamp, clear, el, fitCanvas, fmt, nearestIndex, niceTicks, placeFloating, tickDigits } from './util.js';

const FONT = '11px system-ui, -apple-system, "Segoe UI", sans-serif';

function drawSwatchLine(canvas, color, dash) {
  const { ctx, w, h } = fitCanvas(canvas, 16, 8);
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.setLineDash(dash || []);
  ctx.beginPath();
  ctx.moveTo(1, h / 2);
  ctx.lineTo(w - 1, h / 2);
  ctx.stroke();
}

export class LineChart {
  /**
   * @param {HTMLElement} host
   * @param {object} o  title, sub, series [{key,label,color,dash}], yMin, yMax, minSpan,
   *                    format, height, band {lo,hi,label}, zeroLine, onSeek, xLabel
   */
  constructor(host, o) {
    this.o = { height: 116, format: (v) => fmt(v, 2), minSpan: 0.1, xLabel: 'Tick', ...o };
    this.xs = [];
    this.ys = {};
    this.shade = null;
    this.cursor = null;
    this.hoverIndex = -1;

    clear(host);
    this.legendKeys = [];
    const title = el('div', { class: 'chart-title' }, el('span', { text: this.o.title }), this.o.sub ? el('span', { class: 'chart-sub', text: this.o.sub }) : null);
    let legend = null;
    if (this.o.series.length > 1) {
      legend = el('div', { class: 'chart-legend' });
      for (const s of this.o.series) {
        const sw = el('canvas', { 'aria-hidden': 'true' });
        this.legendKeys.push([sw, s]);
        legend.append(el('span', { class: 'key' }, sw, s.label));
      }
    }
    this.base = el('canvas', { role: 'img', 'aria-label': `${this.o.title} over time` });
    this.overlay = el('canvas', { 'aria-hidden': 'true' });
    this.wrap = el('div', { class: 'chart-canvas-wrap', dataset: { seekable: String(Boolean(this.o.onSeek)) } }, this.base, this.overlay);
    this.tooltip = el('div', { class: 'tooltip', hidden: true });
    this.root = el('div', { class: 'chart' }, title, legend, this.wrap, this.tooltip);
    host.append(this.root);

    this.overlay.addEventListener('pointermove', (e) => this._hover(e));
    this.overlay.addEventListener('pointerleave', () => {
      this.hoverIndex = -1;
      this.tooltip.hidden = true;
      this._drawOverlay();
    });
    this.overlay.addEventListener('click', (e) => {
      if (!this.o.onSeek || !this.xs.length) return;
      const i = this._indexAt(e);
      if (i >= 0) this.o.onSeek(i, this.xs[i]);
    });
    new ResizeObserver(() => this.render()).observe(this.wrap);
  }

  setData(xs, ys, shade = null) {
    this.xs = xs;
    this.ys = ys;
    this.shade = shade;
    this.render();
  }

  setCursor(x) {
    this.cursor = x;
    this._drawOverlay();
  }

  // ------------------------------------------------------------- geometry

  _layout() {
    const w = this.wrap.clientWidth || 300;
    const h = this.o.height;
    const multi = this.o.series.length > 1;
    return { w, h, l: 40, r: multi ? 52 : 10, t: 6, b: 18 };
  }

  _domain() {
    let lo = this.o.yMin ?? Infinity;
    let hi = this.o.yMax ?? -Infinity;
    if (this.o.yMin == null || this.o.yMax == null) {
      let dlo = Infinity;
      let dhi = -Infinity;
      for (const s of this.o.series) {
        for (const v of this.ys[s.key] || []) {
          if (v < dlo) dlo = v;
          if (v > dhi) dhi = v;
        }
      }
      if (this.o.band) {
        dlo = Math.min(dlo, this.o.band.lo);
        dhi = Math.max(dhi, this.o.band.hi);
      }
      if (this.o.zeroLine) {
        dlo = Math.min(dlo, 0);
        dhi = Math.max(dhi, 0);
      }
      if (!Number.isFinite(dlo)) {
        dlo = 0;
        dhi = 1;
      }
      const span = Math.max(this.o.minSpan, dhi - dlo);
      const midpoint = (dlo + dhi) / 2;
      const pad = span * 0.08;
      if (this.o.yMin == null) lo = Math.min(dlo, midpoint - span / 2) - pad;
      if (this.o.yMax == null) hi = Math.max(dhi, midpoint + span / 2) + pad;
    }
    return [lo, hi];
  }

  _scales() {
    const L = this._layout();
    const [ylo, yhi] = this._domain();
    const n = this.xs.length;
    const xlo = n ? this.xs[0] : 0;
    const xhi = n ? Math.max(this.xs[n - 1], xlo + 1) : 1;
    const pw = Math.max(10, L.w - L.l - L.r);
    const ph = Math.max(10, L.h - L.t - L.b);
    const sx = (x) => L.l + ((x - xlo) / (xhi - xlo)) * pw;
    const sy = (y) => L.t + (1 - (y - ylo) / (yhi - ylo)) * ph;
    return { L, sx, sy, xlo, xhi, ylo, yhi, pw, ph };
  }

  _indexAt(e) {
    if (!this.xs.length) return -1;
    const rect = this.overlay.getBoundingClientRect();
    const { L, xlo, xhi, pw } = this._scales();
    const px = clamp(e.clientX - rect.left, L.l, L.l + pw);
    const x = xlo + ((px - L.l) / pw) * (xhi - xlo);
    return nearestIndex(this.xs, x);
  }

  // ---------------------------------------------------------------- draw

  render() {
    const S = this._scales();
    const { L, sx, sy } = S;
    for (const [sw, s] of this.legendKeys) drawSwatchLine(sw, T[s.color], s.dash);
    const { ctx, w, h } = fitCanvas(this.base, L.w, L.h);
    fitCanvas(this.overlay, L.w, L.h);
    ctx.clearRect(0, 0, w, h);
    ctx.font = FONT;

    const top = L.t;
    const bottom = L.h - L.b;
    const n = this.xs.length;

    // Microsleep spans (vertical shading).
    if (this.shade && n) {
      ctx.fillStyle = alpha(T['ink-3'], 0.16);
      let start = -1;
      for (let i = 0; i <= n; i++) {
        const on = i < n && this.shade[i];
        if (on && start < 0) start = i;
        if (!on && start >= 0) {
          const x0 = sx(this.xs[start]);
          const x1 = sx(this.xs[i - 1]) + Math.max(1, S.pw / Math.max(1, S.xhi - S.xlo));
          ctx.fillRect(x0, top, Math.max(1, x1 - x0), bottom - top);
          start = -1;
        }
      }
    }

    // Reference band (e.g. the near-critical kappa range).
    if (this.o.band) {
      const yb0 = sy(this.o.band.hi);
      const yb1 = sy(this.o.band.lo);
      ctx.fillStyle = alpha(T['ink-3'], 0.12);
      ctx.fillRect(L.l, yb0, S.pw, yb1 - yb0);
      ctx.fillStyle = T['ink-3'];
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText(this.o.band.label, L.l + 4, yb0 + 2);
    }

    // Y grid + labels.
    const yt = niceTicks(S.ylo, S.yhi, 3);
    const yd = tickDigits(yt);
    ctx.lineWidth = 1;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (const v of yt) {
      const y = Math.round(sy(v)) + 0.5;
      ctx.strokeStyle = v === 0 && this.o.zeroLine ? T.axis : T.grid;
      ctx.beginPath();
      ctx.moveTo(L.l, y);
      ctx.lineTo(L.l + S.pw, y);
      ctx.stroke();
      ctx.fillStyle = T['ink-3'];
      ctx.fillText(fmt(v, yd), L.l - 6, y);
    }

    // X labels.
    if (n) {
      const xt = niceTicks(S.xlo, S.xhi, Math.max(2, Math.floor(S.pw / 90)));
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillStyle = T['ink-3'];
      for (const v of xt) {
        const x = sx(v);
        if (x < L.l - 1 || x > L.l + S.pw + 1) continue;
        ctx.fillText(String(Math.round(v)), x, bottom + 4);
      }
    }

    // Series.
    const ends = [];
    for (const s of this.o.series) {
      const ys = this.ys[s.key] || [];
      if (!ys.length) continue;
      ctx.strokeStyle = T[s.color];
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.setLineDash(s.dash || []);
      ctx.beginPath();
      if (n > S.pw * 2) {
        // Min/max per pixel column so long runs keep their spikes.
        let col = -1;
        let mn = 0;
        let mx = 0;
        let first = true;
        const flush = () => {
          if (col < 0) return;
          if (first) {
            ctx.moveTo(col, sy(mn));
            first = false;
          } else ctx.lineTo(col, sy(mn));
          ctx.lineTo(col, sy(mx));
        };
        for (let i = 0; i < n; i++) {
          const c = Math.round(sx(this.xs[i]));
          const v = ys[i];
          if (c !== col) {
            flush();
            col = c;
            mn = v;
            mx = v;
          } else {
            if (v < mn) mn = v;
            if (v > mx) mx = v;
          }
        }
        flush();
      } else {
        for (let i = 0; i < n; i++) {
          const x = sx(this.xs[i]);
          const y = sy(ys[i]);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
      ctx.setLineDash([]);
      ends.push({ s, y: sy(ys[ys.length - 1]) });
    }

    // Direct end-labels (2+ series), nudged apart so they never overlap.
    if (this.o.series.length > 1 && ends.length) {
      ends.sort((a, b) => a.y - b.y);
      const gap = 12;
      for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + gap);
      const over = ends[ends.length - 1].y - (bottom - 4);
      if (over > 0) for (const e of ends) e.y -= over;
      for (let i = ends.length - 2; i >= 0; i--) ends[i].y = Math.min(ends[i].y, ends[i + 1].y - gap);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      const x0 = L.l + S.pw + 4;
      for (const e of ends) {
        ctx.strokeStyle = T[e.s.color];
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x0, e.y);
        ctx.lineTo(x0 + 6, e.y);
        ctx.stroke();
        ctx.fillStyle = T['ink-2'];
        ctx.fillText(e.s.short || e.s.label, x0 + 9, e.y);
      }
    }
    this._drawOverlay();
  }

  _drawOverlay() {
    const S = this._scales();
    const { L, sx, sy } = S;
    const { ctx, w, h } = fitCanvas(this.overlay, L.w, L.h);
    ctx.clearRect(0, 0, w, h);
    const top = L.t;
    const bottom = L.h - L.b;

    if (this.cursor != null && this.xs.length) {
      const x = Math.round(sx(this.cursor)) + 0.5;
      ctx.strokeStyle = T['ink-1'];
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x, top);
      ctx.lineTo(x, bottom);
      ctx.stroke();
    }

    const i = this.hoverIndex;
    if (i < 0 || i >= this.xs.length) return;
    const x = Math.round(sx(this.xs[i])) + 0.5;
    ctx.strokeStyle = T['ink-3'];
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.stroke();
    for (const s of this.o.series) {
      const v = (this.ys[s.key] || [])[i];
      if (v === undefined) continue;
      ctx.beginPath();
      ctx.arc(x, sy(v), 4, 0, Math.PI * 2);
      ctx.fillStyle = T[s.color];
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = T.surface;
      ctx.stroke();
    }
  }

  _hover(e) {
    const i = this._indexAt(e);
    if (i < 0) return;
    this.hoverIndex = i;
    this._drawOverlay();
    const tt = this.tooltip;
    clear(tt);
    tt.append(el('div', { class: 'tt-head', text: `${this.o.xLabel} ${Math.round(this.xs[i])}${this.shade && this.shade[i] ? ' · microsleep' : ''}` }));
    for (const s of this.o.series) {
      const v = (this.ys[s.key] || [])[i];
      if (v === undefined) continue;
      const dot = el('span', { class: 'dot' });
      dot.style.background = T[s.color];
      tt.append(el('div', { class: 'tt-row' }, dot, el('span', { class: 'tt-label', text: s.label }), el('span', { class: 'tt-val', text: this.o.format(v) })));
    }
    tt.hidden = false;
    const rect = this.root.getBoundingClientRect();
    placeFloating(tt, this.root, e.clientX - rect.left, e.clientY - rect.top);
  }
}

/** A tiny trend line (no axes) for a value in [min, max]. */
export function drawSparkline(canvas, values, color, { min = 0, max = 1 } = {}) {
  const { ctx, w, h } = fitCanvas(canvas);
  ctx.clearRect(0, 0, w, h);
  if (values.length < 2) return;
  const pad = 3;
  const sx = (i) => pad + (i / (values.length - 1)) * (w - pad * 2);
  const sy = (v) => pad + (1 - (clamp(v, min, max) - min) / (max - min || 1)) * (h - pad * 2);
  ctx.strokeStyle = T.grid;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad, Math.round(sy(min)) + 0.5);
  ctx.lineTo(w - pad, Math.round(sy(min)) + 0.5);
  ctx.stroke();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  values.forEach((v, i) => (i ? ctx.lineTo(sx(i), sy(v)) : ctx.moveTo(sx(i), sy(v))));
  ctx.stroke();
  const last = values.length - 1;
  ctx.beginPath();
  ctx.arc(sx(last), sy(values[last]), 2.5, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

const SUPERSCRIPT = { '-': '⁻', 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹' };
const pow10Label = (e) => (e === 0 ? '1' : e === -1 ? '0.1' : `10${String(e).split('').map((c) => SUPERSCRIPT[c]).join('')}`);

/**
 * Avalanche sizes on log-log axes with a reference line of slope -exponent
 * (1.5 by default). The line is a reference, not a fit: at the default
 * coupling 0.25 the lattice is subcritical (its critical point is 0.5).
 */
export class AvalancheHistogram {
  constructor(host) {
    this.canvas = el('canvas', { class: 'hist', role: 'img', 'aria-label': 'Avalanche size distribution on log-log axes' });
    this.tooltip = el('div', { class: 'tooltip', hidden: true });
    this.wrap = el('div', { class: 'hist-wrap' }, this.canvas, this.tooltip);
    host.append(this.wrap);
    this.data = null;
    this.points = [];
    this.canvas.addEventListener('pointermove', (e) => this._hover(e));
    this.canvas.addEventListener('pointerleave', () => {
      this.tooltip.hidden = true;
    });
    new ResizeObserver(() => this.render()).observe(this.wrap);
  }

  set(data) {
    this.data = data;
    this.render();
  }

  render() {
    const { ctx, w, h } = fitCanvas(this.canvas);
    ctx.clearRect(0, 0, w, h);
    ctx.font = FONT;
    const L = { l: 38, r: 8, t: 8, b: 30 };
    const pw = w - L.l - L.r;
    const ph = h - L.t - L.b;
    const lx0 = 0;
    const lx1 = Math.log10(512);
    const ly0 = -4;
    const ly1 = 0;
    const sx = (x) => L.l + ((Math.log10(x) - lx0) / (lx1 - lx0)) * pw;
    const sy = (y) => L.t + (1 - (Math.log10(y) - ly0) / (ly1 - ly0)) * ph;

    ctx.lineWidth = 1;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'right';
    for (let e = ly0; e <= ly1; e++) {
      const y = Math.round(sy(10 ** e)) + 0.5;
      ctx.strokeStyle = T.grid;
      ctx.beginPath();
      ctx.moveTo(L.l, y);
      ctx.lineTo(L.l + pw, y);
      ctx.stroke();
      ctx.fillStyle = T['ink-3'];
      ctx.fillText(pow10Label(e), L.l - 6, y);
    }
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (const x of [1, 4, 16, 64, 256]) ctx.fillText(String(x), sx(x), L.t + ph + 4);
    ctx.fillText('avalanche size (cells)', L.l + pw / 2, L.t + ph + 16);

    this.points = [];
    const d = this.data;
    if (!d || !d.n) {
      ctx.fillStyle = T['ink-3'];
      ctx.textBaseline = 'middle';
      ctx.fillText('waiting for avalanches…', L.l + pw / 2, L.t + ph / 2);
      return;
    }
    for (let i = 0; i < d.counts.length; i++) {
      if (!d.counts[i] || !d.density[i]) continue;
      const lo = d.edges[i];
      const hi = d.edges[i + 1];
      this.points.push({ x: Math.sqrt(lo * (hi - 1 || 1)), y: d.density[i], lo, hi: hi - 1, count: d.counts[i] });
    }

    // Reference power law through the first point.
    if (this.points.length) {
      const p0 = this.points[0];
      const ref = (x) => p0.y * (x / p0.x) ** -d.exponent;
      ctx.save();
      ctx.beginPath();
      ctx.rect(L.l, L.t, pw, ph);
      ctx.clip();
      ctx.strokeStyle = T['ink-3'];
      ctx.setLineDash([5, 4]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(sx(1), sy(ref(1)));
      ctx.lineTo(sx(512), sy(ref(512)));
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = T['ink-3'];
      ctx.textAlign = 'right';
      ctx.textBaseline = 'top';
      ctx.fillText(`reference slope −${d.exponent}`, L.l + pw, L.t + 2);
    }

    for (const p of this.points) {
      p.px = sx(p.x);
      p.py = sy(Math.max(p.y, 1e-4));
      ctx.beginPath();
      ctx.arc(p.px, p.py, 4, 0, Math.PI * 2);
      ctx.fillStyle = T['ink-1'];
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = T.surface;
      ctx.stroke();
    }
  }

  _hover(e) {
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    let best = null;
    let bestD = 14;
    for (const p of this.points) {
      const dd = Math.hypot(p.px - x, p.py - y);
      if (dd < bestD) {
        bestD = dd;
        best = p;
      }
    }
    if (!best) {
      this.tooltip.hidden = true;
      return;
    }
    const pct = (100 * best.count) / this.data.n;
    clear(this.tooltip);
    this.tooltip.append(
      el('div', { class: 'tt-head', text: best.lo === best.hi ? `size ${best.lo}` : `size ${best.lo}–${best.hi}` }),
      el('div', { class: 'tt-row' }, el('span', { class: 'tt-label', text: 'avalanches' }), el('span', { class: 'tt-val', text: `${best.count} (${pct.toFixed(0)}%)` })),
    );
    this.tooltip.hidden = false;
    placeFloating(this.tooltip, this.wrap, x, y);
  }
}

/** Horizontal kappa gauge with the 0.85-1.05 band the regime chip uses (an estimator band, not the lattice's critical point). */
export function drawKappaGauge(canvas, kappa, measuring) {
  const { ctx, w, h } = fitCanvas(canvas);
  ctx.clearRect(0, 0, w, h);
  ctx.font = FONT;
  const lo = 0.4;
  const hi = 1.6;
  const l = 8;
  const r = 8;
  const pw = w - l - r;
  const sx = (v) => l + ((clamp(v, lo, hi) - lo) / (hi - lo)) * pw;
  const y = 18;

  ctx.fillStyle = alpha(T['ink-3'], 0.18);
  ctx.fillRect(sx(0.85), y - 7, sx(1.05) - sx(0.85), 14);
  ctx.strokeStyle = T.axis;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(l, y);
  ctx.lineTo(l + pw, y);
  ctx.stroke();

  ctx.fillStyle = T['ink-3'];
  ctx.textBaseline = 'top';
  ctx.textAlign = 'center';
  for (const v of [0.5, 0.75, 1.0, 1.25, 1.5]) {
    ctx.fillRect(Math.round(sx(v)), y + 4, 1, 4);
    ctx.fillText(v.toFixed(2).replace(/0$/, ''), sx(v), y + 10);
  }
  ctx.textBaseline = 'bottom';
  ctx.textAlign = 'left';
  ctx.fillText('subcritical', l, y - 8);
  ctx.textAlign = 'right';
  ctx.fillText('supercritical', l + pw, y - 8);
  ctx.textAlign = 'center';
  ctx.fillText('critical', sx(0.95), y - 8);

  if (measuring) return;
  const x = sx(kappa);
  ctx.fillStyle = T['ink-1'];
  ctx.strokeStyle = T.surface;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x, y + 6);
  ctx.lineTo(x - 6, y - 6);
  ctx.lineTo(x + 6, y - 6);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
}
