// Entry point: theme, tabs (Live / Replay) and the two controllers.

import { LiveController } from './live.js';
import { ReplayController } from './replay.js';
import { initTheme } from './theme.js';
import { $, toast } from './util.js';

initTheme();

const tabs = { live: $('#tab-live'), replay: $('#tab-replay') };
const views = { live: $('#view-live'), replay: $('#view-replay') };

const replay = new ReplayController();
const live = new LiveController({
  onRecorded: async (runId) => {
    show('replay');
    await replay.openRun(runId);
  },
});

function show(name, { push = true } = {}) {
  for (const key of Object.keys(tabs)) {
    const on = key === name;
    tabs[key].setAttribute('aria-selected', String(on));
    tabs[key].tabIndex = on ? 0 : -1;
    views[key].hidden = !on;
  }
  live.setActive(name === 'live');
  replay.setActive(name === 'replay');
  if (push) {
    const url = new URL(window.location.href);
    url.pathname = name === 'replay' ? '/replay' : '/live';
    window.history.replaceState(null, '', url);
  }
}

for (const [name, tab] of Object.entries(tabs)) {
  tab.addEventListener('click', () => show(name));
  tab.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      const next = name === 'live' ? 'replay' : 'live';
      show(next);
      tabs[next].focus();
    }
  });
}

const initial = window.location.pathname.startsWith('/replay') ? 'replay' : 'live';
show(initial, { push: false });
live.init().catch((err) => toast(err.message, { level: 'critical', ms: 15000 }));
