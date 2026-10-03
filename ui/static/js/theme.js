// Theme tokens. Canvas drawing reads colours from the CSS custom properties so
// the stylesheet stays the single source of truth for both themes.

import { store } from './util.js';

const KEY = 'quantum-rat-theme';
const NAMES = [
  'page', 'surface', 'raised', 'floor', 'ink-1', 'ink-2', 'ink-3', 'grid', 'axis',
  'da', 'ne', 'ach', 'ht', 'pos', 'neg', 'mid', 'good', 'good-text', 'warning',
  'serious', 'critical',
];

/** Current colour tokens, e.g. T['ink-1'], T.da. Refreshed on theme change. */
export const T = {};

const listeners = new Set();

function readTokens() {
  const style = getComputedStyle(document.documentElement);
  for (const name of NAMES) T[name] = style.getPropertyValue(`--${name}`).trim();
}

function systemPrefersLight() {
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
}

export function currentTheme() {
  const stamped = document.documentElement.dataset.theme;
  if (stamped) return stamped;
  return systemPrefersLight() ? 'light' : 'dark';
}

function apply(theme) {
  if (theme) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
  readTokens();
  const btn = document.getElementById('theme-toggle');
  if (btn) {
    const next = currentTheme() === 'dark' ? 'light' : 'dark';
    btn.setAttribute('aria-label', `Switch to ${next} theme`);
    btn.title = `Switch to ${next} theme`;
  }
  for (const fn of listeners) fn();
}

export function onThemeChange(fn) {
  listeners.add(fn);
}

export function initTheme() {
  const saved = store.get(KEY);
  apply(saved === 'light' || saved === 'dark' ? saved : null);
  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    const next = currentTheme() === 'dark' ? 'light' : 'dark';
    store.set(KEY, next);
    apply(next);
  });
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: light)').addEventListener?.('change', () => {
      if (!store.get(KEY)) apply(null);
    });
  }
}

/** The four neuromodulators, in their fixed categorical order. */
export const MODULATORS = [
  { key: 'da', mod: 'DA', name: 'Dopamine', role: 'Reward minus its running mean (1.0 on a reward); low DA boosts the forward drive' },
  { key: 'ne', mod: 'NE', name: 'Norepinephrine', role: '½ pain + ½ the novelty bit; scales pain avoidance and freezing' },
  { key: 'ach', mod: 'ACh', name: 'Acetylcholine', role: 'Equals the novelty bit (checksum change); scales vision drive' },
  { key: 'ht', mod: '5HT', name: 'Serotonin', role: 'Running mean of reward, lagging DA\'s input; adds patience to rest' },
];
