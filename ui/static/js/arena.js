// Top-down arena: floor, value map, objects, pain zones, vision rays, whiskers,
// trail, the true body and the path-integration estimate ("ghost").
// Shared by the live console and the replay viewer.

import { T } from './theme.js';
import { alpha, clear, el, fitCanvas, fmt, fmtSigned, headingDeg, mix, placeFloating, rafThrottle } from './util.js';

const BODY_LEN = 0.75; // metres, nose to tail
const WHISKER_ANGLE = 0.8;

const KIND_LABEL = { hazard: 'hazard', hidden: 'hidden goal', collected: 'eaten food' };

export class ArenaView {
  constructor(canvas, hoverEl) {
    this.canvas = canvas;
    this.hoverEl = hoverEl;
    this.s = {
      bounds: [10, 10],
      objects: [],
      painZone: 1.5,
      valueMap: null,
      trail: [],
      path: null, // replay: the full path, drawn faint underneath the trail
      agent: null,
      estimate: null,
      rays: [],
      range: 12,
      fov: 1.2,
      whiskers: [false, false],
      pain: 0,
      replayCell: null,
      microsleep: false,
      targetLabel: 'target',
      layers: { value: true, rays: true, trail: true, estimate: true },
    };
    this._valueIndex = new Map();
    this.render = rafThrottle(() => this._render());
    new ResizeObserver(() => this._render()).observe(canvas);
    canvas.addEventListener('pointermove', (e) => this._hover(e));
    canvas.addEventListener('pointerleave', () => {
      if (this.hoverEl) this.hoverEl.hidden = true;
    });
  }

  set(partial) {
    Object.assign(this.s, partial);
    if ('valueMap' in partial) this._indexValues();
    this.render();
  }

  setLayer(name, on) {
    this.s.layers = { ...this.s.layers, [name]: on };
    this.render();
  }

  _indexValues() {
    this._valueIndex.clear();
    const vm = this.s.valueMap;
    if (!vm || !vm.cells) return;
    for (const [cx, cy, v] of vm.cells) {
      this._valueIndex.set(`${Math.floor(cx / vm.cell)},${Math.floor(cy / vm.cell)}`, v);
    }
  }

  valueAt(x, y) {
    const vm = this.s.valueMap;
    if (!vm || !vm.cell) return undefined;
    return this._valueIndex.get(`${Math.floor(x / vm.cell)},${Math.floor(y / vm.cell)}`);
  }

  // ---------------------------------------------------------------- geometry

  _frame() {
    const w = this.canvas.clientWidth || 400;
    const [bx, by] = this.s.bounds;
    const m = 10;
    const half = Math.max(bx, by);
    const k = (w - 2 * m) / (2 * half);
    return {
      w,
      k,
      X: (x) => w / 2 + x * k,
      Y: (y) => w / 2 - y * k,
      toWorld: (px, py) => [(px - w / 2) / k, (w / 2 - py) / k],
    };
  }

  // -------------------------------------------------------------------- draw

  _render() {
    const { ctx, w } = fitCanvas(this.canvas, this.canvas.clientWidth, this.canvas.clientWidth);
    const F = this._frame();
    const { X, Y, k } = F;
    const s = this.s;
    const [bx, by] = s.bounds;
    ctx.clearRect(0, 0, w, w);

    // Floor + 2 m grid.
    ctx.fillStyle = T.floor;
    ctx.fillRect(X(-bx), Y(by), 2 * bx * k, 2 * by * k);
    ctx.strokeStyle = T.grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let g = -bx + 2; g < bx; g += 2) {
      const x = Math.round(X(g)) + 0.5;
      ctx.moveTo(x, Y(by));
      ctx.lineTo(x, Y(-by));
    }
    for (let g = -by + 2; g < by; g += 2) {
      const y = Math.round(Y(g)) + 0.5;
      ctx.moveTo(X(-bx), y);
      ctx.lineTo(X(bx), y);
    }
    ctx.stroke();

    ctx.save();
    ctx.beginPath();
    ctx.rect(X(-bx), Y(by), 2 * bx * k, 2 * by * k);
    ctx.clip();

    // Value map (diverging: blue = valuable, red = to be avoided).
    const vm = s.valueMap;
    if (s.layers.value && vm && vm.cells && vm.cells.length && vm.max > 0) {
      const c = vm.cell;
      for (const [cx, cy, v] of vm.cells) {
        const t = Math.min(1, Math.abs(v) / vm.max) ** 0.5;
        ctx.fillStyle = mix(T.mid, v > 0 ? T.pos : T.neg, t);
        ctx.globalAlpha = 0.3 + 0.6 * t;
        ctx.fillRect(X(cx - c / 2), Y(cy + c / 2), c * k + 0.5, c * k + 0.5);
      }
      ctx.globalAlpha = 1;
    }

    // Pain zones around hazards.
    for (const o of s.objects) {
      if (o.kind !== 'hazard') continue;
      const r0 = o.r * k;
      const r1 = (o.r + s.painZone) * k;
      const g = ctx.createRadialGradient(X(o.x), Y(o.y), r0, X(o.x), Y(o.y), r1);
      g.addColorStop(0, alpha(T.critical, 0.32));
      g.addColorStop(1, alpha(T.critical, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(X(o.x), Y(o.y), r1, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = alpha(T.critical, 0.55);
      ctx.setLineDash([3, 4]);
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Full recorded path (replay), faint.
    if (s.path && s.layers.trail) this._polyline(ctx, F, s.path, alpha(T['ink-3'], 0.45), 1.5);

    // Trail, fading with age.
    if (s.trail.length > 1) {
      const chunks = 6;
      const n = s.trail.length;
      for (let c = 0; c < chunks; c++) {
        const a = Math.floor((c * (n - 1)) / chunks);
        const b = Math.floor(((c + 1) * (n - 1)) / chunks);
        if (!s.layers.trail && c < chunks - 1) continue;
        this._polyline(ctx, F, s.trail.slice(a, b + 1), alpha(T['ink-2'], 0.15 + (0.7 * (c + 1)) / chunks), 2);
      }
    }

    // Replay highlight: the place the sleeping brain is replaying.
    if (s.replayCell && vm) {
      const c = vm.cell || 0.5;
      const [rx, ry] = s.replayCell;
      ctx.strokeStyle = T['ink-1'];
      ctx.lineWidth = 2;
      ctx.setLineDash([3, 3]);
      ctx.strokeRect(X(rx - c), Y(ry + c), 2 * c * k, 2 * c * k);
      ctx.setLineDash([]);
      this._label(ctx, 'replay', X(rx), Y(ry + c) - 4, 'bottom');
    }

    // Objects.
    for (const o of s.objects) this._object(ctx, F, o);

    const a = s.agent;
    // Vision fan + rays.
    if (a && s.layers.rays && s.rays.length) {
      const half = s.fov / 2;
      ctx.fillStyle = alpha(T['ink-3'], 0.07);
      ctx.beginPath();
      ctx.moveTo(X(a.x), Y(a.y));
      ctx.arc(X(a.x), Y(a.y), s.range * k, -(a.heading + half), -(a.heading - half));
      ctx.closePath();
      ctx.fill();
      for (const [ang, dist, kind] of s.rays) {
        const phi = a.heading + ang;
        const ex = a.x + Math.cos(phi) * dist;
        const ey = a.y + Math.sin(phi) * dist;
        const color = this._rayColor(kind);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.setLineDash(kind === 'none' ? [2, 4] : []);
        ctx.beginPath();
        ctx.moveTo(X(a.x), Y(a.y));
        ctx.lineTo(X(ex), Y(ey));
        ctx.stroke();
        ctx.setLineDash([]);
        if (kind !== 'none') {
          ctx.beginPath();
          ctx.arc(X(ex), Y(ey), 3, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
        }
      }
    }

    // Estimate ghost (where path integration thinks the body is).
    const e = s.estimate;
    if (a && e && s.layers.estimate) {
      const drift = Math.hypot(e.x - a.x, e.y - a.y);
      if (drift > 0.15) {
        ctx.strokeStyle = T['ink-3'];
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(X(a.x), Y(a.y));
        ctx.lineTo(X(e.x), Y(e.y));
        ctx.stroke();
        ctx.setLineDash([]);
      }
      this._body(ctx, F, e, { ghost: true });
    }

    if (a) {
      // Whiskers.
      if (s.layers.rays) {
        const tipX = a.x + Math.cos(a.heading) * BODY_LEN * 0.5;
        const tipY = a.y + Math.sin(a.heading) * BODY_LEN * 0.5;
        [WHISKER_ANGLE, -WHISKER_ANGLE].forEach((off, i) => {
          const hit = s.whiskers[i];
          const phi = a.heading + off;
          ctx.strokeStyle = hit ? T['ink-1'] : alpha(T['ink-2'], 0.8);
          ctx.lineWidth = hit ? 2.5 : 1.25;
          ctx.beginPath();
          ctx.moveTo(X(tipX), Y(tipY));
          ctx.lineTo(X(tipX + Math.cos(phi) * 0.9), Y(tipY + Math.sin(phi) * 0.9));
          ctx.stroke();
        });
      }
      if (s.pain > 0.05) {
        ctx.strokeStyle = alpha(T.critical, 0.4 + 0.6 * Math.min(1, s.pain));
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(X(a.x), Y(a.y), Math.max(BODY_LEN * k * 0.8, 14), 0, Math.PI * 2);
        ctx.stroke();
      }
      this._body(ctx, F, a, {});
      if (s.microsleep) this._label(ctx, 'z z z', X(a.x) + 12, Y(a.y) - 12, 'bottom', T['ink-1']);
    }
    ctx.restore();

    // Walls.
    ctx.strokeStyle = T['ink-3'];
    ctx.lineWidth = 2;
    ctx.strokeRect(X(-bx), Y(by), 2 * bx * k, 2 * by * k);

    // Scale bar.
    const sbx = X(-bx) + 10;
    const sby = Y(-by) - 12;
    ctx.strokeStyle = T['ink-2'];
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(sbx, sby);
    ctx.lineTo(sbx + 2 * k, sby);
    ctx.stroke();
    this._label(ctx, '2 m', sbx + k, sby - 4, 'bottom');
  }

  _polyline(ctx, F, pts, color, width) {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.beginPath();
    let pen = false;
    for (const p of pts) {
      if (!p) {
        pen = false;
        continue;
      }
      if (pen) ctx.lineTo(F.X(p[0]), F.Y(p[1]));
      else ctx.moveTo(F.X(p[0]), F.Y(p[1]));
      pen = true;
    }
    ctx.stroke();
  }

  _label(ctx, text, x, y, baseline = 'middle', color) {
    ctx.font = '11px system-ui, -apple-system, "Segoe UI", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = baseline;
    ctx.lineWidth = 3;
    ctx.strokeStyle = T.floor;
    ctx.strokeText(text, x, y);
    ctx.fillStyle = color || T['ink-2'];
    ctx.fillText(text, x, y);
  }

  _rayColor(kind) {
    if (kind === 'target') return T.good;
    if (kind === 'hazard') return T.critical;
    if (kind === 'wall') return alpha(T['ink-3'], 0.85);
    if (kind === 'none') return alpha(T['ink-3'], 0.4);
    return T['ink-2'];
  }

  _object(ctx, F, o) {
    const { X, Y, k } = F;
    const r = o.r * k;
    ctx.beginPath();
    ctx.arc(X(o.x), Y(o.y), r, 0, Math.PI * 2);
    if (o.kind === 'target') {
      ctx.fillStyle = T.good;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = T.floor;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(X(o.x), Y(o.y), r * 0.42, 0, Math.PI * 2);
      ctx.fillStyle = T.floor;
      ctx.fill();
    } else if (o.kind === 'hazard') {
      ctx.fillStyle = T.critical;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = T.floor;
      ctx.stroke();
      ctx.fillStyle = '#ffffff';
      ctx.font = `bold ${Math.max(11, Math.round(r))}px system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('!', X(o.x), Y(o.y) + 1);
    } else {
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = o.kind === 'hidden' ? T['ink-2'] : alpha(T['ink-3'], 0.7);
      ctx.stroke();
      ctx.setLineDash([]);
      if (o.kind === 'hidden') this._label(ctx, 'hidden goal', X(o.x), Y(o.y) + r + 4, 'top');
    }
  }

  _body(ctx, F, pose, { ghost }) {
    const { X, Y, k } = F;
    const len = Math.max(BODY_LEN * k, 16);
    const wid = len * 0.56;
    ctx.save();
    ctx.translate(X(pose.x), Y(pose.y));
    ctx.rotate(-pose.heading);
    ctx.beginPath();
    // Teardrop: rounded rump, pointed nose along +x.
    ctx.moveTo(len * 0.55, 0);
    ctx.quadraticCurveTo(len * 0.1, wid * 0.62, -len * 0.3, wid * 0.42);
    ctx.quadraticCurveTo(-len * 0.55, 0, -len * 0.3, -wid * 0.42);
    ctx.quadraticCurveTo(len * 0.1, -wid * 0.62, len * 0.55, 0);
    ctx.closePath();
    if (ghost) {
      ctx.setLineDash([3, 3]);
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = T['ink-2'];
      ctx.stroke();
      ctx.setLineDash([]);
    } else {
      ctx.fillStyle = T['ink-1'];
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = T.floor;
      ctx.stroke();
      // Eye, so heading reads at a glance.
      ctx.beginPath();
      ctx.arc(len * 0.2, -wid * 0.14, Math.max(1.5, len * 0.05), 0, Math.PI * 2);
      ctx.fillStyle = T.floor;
      ctx.fill();
    }
    ctx.restore();
  }

  // ------------------------------------------------------------------- hover

  _hover(e) {
    if (!this.hoverEl) return;
    const rect = this.canvas.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const F = this._frame();
    const [x, y] = F.toWorld(px, py);
    const [bx, by] = this.s.bounds;
    if (Math.abs(x) > bx || Math.abs(y) > by) {
      this.hoverEl.hidden = true;
      return;
    }
    const lines = [el('div', {}, el('span', { class: 'muted', text: 'x ' }), fmt(x, 2), el('span', { class: 'muted', text: '  y ' }), fmt(y, 2), el('span', { class: 'muted', text: ' m' }))];
    const v = this.valueAt(x, y);
    if (v !== undefined) lines.push(el('div', {}, el('span', { class: 'muted', text: 'learned value ' }), fmtSigned(v, 3)));
    let nearest = null;
    for (const o of this.s.objects) {
      const d = Math.hypot(o.x - x, o.y - y) - o.r;
      if (!nearest || d < nearest.d) nearest = { o, d };
    }
    if (nearest) {
      const label = nearest.o.kind === 'target' ? this.s.targetLabel : KIND_LABEL[nearest.o.kind] || nearest.o.kind;
      lines.push(el('div', {}, el('span', { class: 'muted', text: `${label} ` }), nearest.d <= 0 ? 'here' : `${fmt(nearest.d, 1)} m away`));
    }
    const a = this.s.agent;
    if (a && Math.hypot(a.x - x, a.y - y) < 0.8) {
      lines.push(el('div', {}, el('span', { class: 'muted', text: 'agent heading ' }), `${fmt(headingDeg(a.heading), 0)}°`));
    }
    clear(this.hoverEl).append(...lines);
    this.hoverEl.hidden = false;
    placeFloating(this.hoverEl, this.canvas.parentElement, px, py);
  }
}

// --------------------------------------------------------------------- legend

function glyph(draw, w = 18, h = 14) {
  const c = el('canvas', { class: 'legend-swatch', 'aria-hidden': 'true' });
  requestAnimationFrame(() => {
    const { ctx } = fitCanvas(c, w, h);
    ctx.clearRect(0, 0, w, h);
    draw(ctx, w, h);
  });
  return c;
}

/**
 * Build the arena legend for the kinds actually present.
 * @param {HTMLElement} host
 * @param {object} o  {kinds:Set, targetLabel, value:boolean, rays:boolean, estimate:boolean, path:boolean}
 */
export function buildArenaLegend(host, o) {
  clear(host);
  const item = (g, label) => host.append(el('span', { class: 'legend-item' }, g, label));
  item(
    glyph((ctx, w, h) => {
      ctx.fillStyle = T['ink-1'];
      ctx.beginPath();
      ctx.moveTo(w - 2, h / 2);
      ctx.quadraticCurveTo(w * 0.5, h - 1, 3, h * 0.72);
      ctx.quadraticCurveTo(0, h / 2, 3, h * 0.28);
      ctx.quadraticCurveTo(w * 0.5, 1, w - 2, h / 2);
      ctx.fill();
    }),
    'Agent (true position)',
  );
  if (o.estimate) {
    item(
      glyph((ctx, w, h) => {
        ctx.strokeStyle = T['ink-2'];
        ctx.setLineDash([3, 2]);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(w - 2, h / 2);
        ctx.quadraticCurveTo(w * 0.5, h - 1, 3, h * 0.72);
        ctx.quadraticCurveTo(0, h / 2, 3, h * 0.28);
        ctx.quadraticCurveTo(w * 0.5, 1, w - 2, h / 2);
        ctx.stroke();
      }),
      'Where it thinks it is',
    );
  }
  if (o.kinds.has('target')) {
    item(
      glyph((ctx, w, h) => {
        ctx.fillStyle = T.good;
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = T.surface;
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }),
      o.targetLabel[0].toUpperCase() + o.targetLabel.slice(1),
    );
  }
  if (o.kinds.has('hazard')) {
    item(
      glyph((ctx, w, h) => {
        ctx.fillStyle = alpha(T.critical, 0.3);
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, 7, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = T.critical;
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, 4, 0, Math.PI * 2);
        ctx.fill();
      }),
      'Hazard + pain zone',
    );
  }
  if (o.kinds.has('hidden') || o.kinds.has('collected')) {
    item(
      glyph((ctx, w, h) => {
        ctx.strokeStyle = T['ink-2'];
        ctx.setLineDash([3, 2]);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, 5.5, 0, Math.PI * 2);
        ctx.stroke();
      }),
      o.kinds.has('hidden') ? 'Hidden goal (invisible to the agent)' : 'Eaten food',
    );
  }
  if (o.rays) {
    item(
      glyph((ctx, w, h) => {
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = alpha(T['ink-3'], 0.85);
        ctx.beginPath();
        ctx.moveTo(1, h - 2);
        ctx.lineTo(w - 3, 3);
        ctx.stroke();
        ctx.fillStyle = alpha(T['ink-3'], 0.85);
        ctx.beginPath();
        ctx.arc(w - 3, 3, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }),
      'Vision ray (coloured by what it hits)',
    );
  }
  if (o.path) {
    item(
      glyph((ctx, w, h) => {
        ctx.strokeStyle = alpha(T['ink-3'], 0.6);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(1, h / 2);
        ctx.lineTo(w - 1, h / 2);
        ctx.stroke();
      }),
      'Whole run',
    );
  }
  if (o.value) {
    const ramp = el('canvas', { 'aria-hidden': 'true' });
    requestAnimationFrame(() => {
      const { ctx, w, h } = fitCanvas(ramp, 72, 10);
      for (let i = 0; i < w; i++) {
        const t = (i / (w - 1)) * 2 - 1;
        ctx.fillStyle = mix(T.mid, t > 0 ? T.pos : T.neg, Math.abs(t) ** 0.5);
        ctx.fillRect(i, 0, 1, h);
      }
    });
    host.append(
      el('span', { class: 'legend-ramp', title: 'Drawn where the brain thinks each place is, so it drifts with path integration' }, 'Learned value (in the brain’s own coordinates)', el('span', { class: 'muted', text: 'avoid' }), ramp, el('span', { text: 'seek' })),
    );
  }
}
