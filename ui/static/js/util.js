// Small DOM, formatting and canvas helpers shared by every view.

/** Create an element: el('div', {class: 'x', text: 'hi'}, child, ...). */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

// ------------------------------------------------------------------ numbers

export function fmt(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (typeof value !== 'number') return String(value);
  if (!Number.isFinite(value)) return value > 0 ? '∞' : '−∞';
  return value.toFixed(digits).replace('-', '−');
}

export function fmtSigned(value, digits = 2) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fmt(value, digits);
  const s = Math.abs(value).toFixed(digits);
  if (Number(s) === 0) return s;
  return (value > 0 ? '+' : '−') + s;
}

export function fmtInt(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fmt(value);
  return Math.round(value).toLocaleString('en-US');
}

/** Pretty-print anything for a readout cell. */
export function fmtAny(value) {
  if (typeof value === 'number') return Number.isInteger(value) ? fmtInt(value) : fmt(value, 3);
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (value === null || value === undefined || value === '') return '—';
  if (Array.isArray(value)) return value.map(fmtAny).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export const deg = (rad) => (rad * 180) / Math.PI;

/** Compass-style heading in degrees, [0, 360). */
export const headingDeg = (rad) => ((deg(rad) % 360) + 360) % 360;

/** Wrap an angle into (-pi, pi]. */
export function wrapAngle(a) {
  let x = (a + Math.PI) % (2 * Math.PI);
  if (x < 0) x += 2 * Math.PI;
  return x - Math.PI;
}

export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

/** "Nice" axis ticks covering [lo, hi]. */
export function niceTicks(lo, hi, count = 4) {
  if (!(hi > lo)) return [lo];
  const span = hi - lo;
  const raw = span / Math.max(1, count);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const start = Math.ceil(lo / step - 1e-9) * step;
  const ticks = [];
  for (let v = start; v <= hi + step * 1e-9; v += step) ticks.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  return ticks;
}

export function tickDigits(ticks) {
  if (ticks.length < 2) return 2;
  const step = Math.abs(ticks[1] - ticks[0]);
  return step >= 1 ? 0 : Math.min(3, Math.ceil(-Math.log10(step)));
}

/** Index of the element of sorted `xs` nearest to `x`. */
export function nearestIndex(xs, x) {
  let lo = 0;
  let hi = xs.length - 1;
  if (hi < 0) return -1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= x) lo = mid;
    else hi = mid;
  }
  return Math.abs(xs[lo] - x) <= Math.abs(xs[hi] - x) ? lo : hi;
}

// ------------------------------------------------------------------ colours

function parseHex(hex) {
  const h = hex.trim().replace('#', '');
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  const n = parseInt(full.slice(0, 6), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** rgba() string for a hex colour (or pass through rgba/other strings). */
export function alpha(color, a) {
  if (!color || !color.startsWith('#')) return color;
  const [r, g, b] = parseHex(color);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

/** Linear mix of two hex colours, t in [0, 1]. */
export function mix(c1, c2, t) {
  const a = parseHex(c1);
  const b = parseHex(c2);
  const m = a.map((v, i) => Math.round(v + (b[i] - v) * t));
  return `rgb(${m[0]}, ${m[1]}, ${m[2]})`;
}

// ------------------------------------------------------------------- canvas

/**
 * Size a canvas's backing store to its CSS box at the device pixel ratio and
 * return a context drawing in CSS pixels. Height defaults to the CSS height.
 */
export function fitCanvas(canvas, width, height) {
  const dpr = window.devicePixelRatio || 1;
  const w = Math.max(1, Math.round(width ?? canvas.clientWidth));
  const h = Math.max(1, Math.round(height ?? canvas.clientHeight));
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}

/** Run `fn` at most once per animation frame. */
export function rafThrottle(fn) {
  let queued = false;
  let lastArgs = [];
  return (...args) => {
    lastArgs = args;
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      fn(...lastArgs);
    });
  };
}

export function debounce(fn, ms) {
  let timer = null;
  const wrapped = (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
  wrapped.flush = (...args) => {
    clearTimeout(timer);
    fn(...args);
  };
  return wrapped;
}

/** Position a floating box near (x, y) inside `host`, flipping at the edges. */
export function placeFloating(box, host, x, y, offset = 14) {
  const hw = host.clientWidth;
  const hh = host.clientHeight;
  const bw = box.offsetWidth;
  const bh = box.offsetHeight;
  let left = x + offset;
  let top = y + offset;
  if (left + bw > hw) left = x - offset - bw;
  if (top + bh > hh) top = y - offset - bh;
  box.style.left = `${Math.max(0, left)}px`;
  box.style.top = `${Math.max(0, top)}px`;
}

// -------------------------------------------------------------------- toast

let toastTimer = null;

/** Show a transient message; `action` = {label, onClick} adds a button. */
export function toast(message, { level = 'info', action = null, ms = 4500 } = {}) {
  const box = document.getElementById('toast');
  if (!box) return;
  clear(box);
  box.dataset.level = level;
  box.append(el('span', { text: message }));
  if (action) {
    box.append(
      el('button', {
        class: 'btn',
        type: 'button',
        text: action.label,
        onclick: () => {
          box.hidden = true;
          action.onClick();
        },
      }),
    );
  }
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    box.hidden = true;
  }, ms);
}

/** localStorage that never throws (private windows, blocked storage). */
export const store = {
  get(key, fallback = null) {
    try {
      const v = window.localStorage.getItem(key);
      return v === null ? fallback : v;
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch {
      /* storage unavailable: preference just isn't remembered */
    }
  },
};
