// App shell: auth gate, layout, hash router.
import { api, setCsrf, setUnauthorizedHandler } from './api.js';
import { h, icon, state, toast, toastErr, createPoller, confirmDialog, clear, $, $$ } from './ui.js';

const ROUTES = [
  { id: 'dashboard', label: 'Dashboard', icon: 'home' },
  { id: 'recap-studio', label: 'Recap Studio', icon: 'film' },
  { id: 'research', label: 'AI Research', icon: 'search' },
  { id: 'script', label: 'Script Editor', icon: 'script' },
  { id: 'voice', label: 'Voice Studio', icon: 'mic' },
  { id: 'subtitles', label: 'Subtitle Studio', icon: 'captions' },
  { id: 'renderer', label: 'Video Renderer', icon: 'video' },
  { id: 'projects', label: 'Projects', icon: 'folder' },
  { id: 'platforms', label: 'Platforms', icon: 'share' },
  { id: 'automation', label: 'Automation', icon: 'zap' },
  { id: 'analytics', label: 'Analytics', icon: 'chart' },
  { id: 'settings', label: 'Settings', icon: 'settings' },
];
const BOTTOM = ['dashboard', 'recap-studio', 'projects', 'renderer'];
const app = document.getElementById('app');

let shell = null, current = null, poller = null, dirtyFn = null, lastHash = '', navToken = 0;

const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
};

/* ---------- auth ---------- */
function loginScreen(session, notice) {
  teardownPage();
  shell = null;
  const configured = session?.configured !== false;
  const err = h('p', { class: 'txt-err sm', role: 'alert' }, notice || '');
  const pw = h('input', { type: 'password', id: 'pw', autocomplete: 'current-password', required: true, disabled: !configured, 'data-autofocus': '' });
  const btn = h('button', { class: 'btn primary lg', type: 'submit', disabled: !configured }, icon('lock', 16), 'Sign in');
  const form = h('form', { class: 'stack', onsubmit: async (e) => {
    e.preventDefault(); err.textContent = ''; btn.disabled = true;
    try {
      const r = await api.post('/api/auth/login', { password: pw.value }, { noAuthRedirect: true });
      setCsrf(r.csrf);
      await start();
    } catch (x) { err.textContent = x.message; btn.disabled = false; pw.select(); }
  } },
    h('div', { class: 'field' }, h('label', { for: 'pw' }, 'Admin password'), pw), err, btn);
  clear(app).append(h('main', { class: 'login' }, h('div', { class: 'login-card' },
    h('div', { class: 'brand' }, h('div', { class: 'brand-mark' }, 'N'), h('div', { class: 'brand-t' }, h('b', {}, 'NEXORA'), h('span', {}, 'Myanmar Recap Studio'))),
    h('h1', {}, 'Sign in'),
    configured ? h('p', { class: 'muted' }, 'Enter the studio password to continue.')
      : h('div', { class: 'banner warn', role: 'alert' }, icon('alert'), h('div', {}, h('b', {}, 'Server setup required. '), 'No admin password is configured. Set ', h('code', { class: 'mono' }, 'NEXORA_ADMIN_PASSWORD'), ' in the server environment and restart the backend, then reload this page.')),
    form)));
  if (configured) setTimeout(() => pw.focus(), 30);
}

async function start() {
  let session;
  try { session = await api.get('/api/auth/session', null, { noAuthRedirect: true }); }
  catch (e) {
    clear(app).append(h('div', { class: 'login' }, h('div', { class: 'login-card' }, h('h1', {}, 'Backend unreachable'), h('p', { class: 'muted' }, e.message), h('button', { class: 'btn primary', onclick: start }, icon('refresh', 16), 'Retry'))));
    return;
  }
  if (!session.authenticated) { loginScreen(session); return; }
  setCsrf(session.csrf);
  state.role = session.role; state.readOnly = session.role !== 'admin';
  buildShell();
  route();
}

async function logout() {
  try { await api.post('/api/auth/logout', {}); } catch { /* ignore */ }
  setCsrf(null); state.role = null;
  loginScreen({ configured: true, authenticated: false });
}

setUnauthorizedHandler(() => { if (shell) { setCsrf(null); loginScreen({ configured: true }, 'Your session expired. Please sign in again.'); } });

/* ---------- layout ---------- */
function navLink(r) {
  return h('a', { href: `#/${r.id}`, 'data-route': r.id, onclick: () => shell.classList.remove('drawer-open') }, icon(r.icon, 19), h('span', { class: 'lbl' }, r.label));
}
function buildShell() {
  const collapse = h('button', { class: 'btn ghost collapse-btn', 'aria-label': 'Toggle sidebar', onclick: () => { const c = shell.classList.toggle('collapsed'); store.set('nx_collapsed', c ? '1' : '0'); } }, icon('sidebar', 19), h('span', { class: 'lbl' }, 'Collapse'));
  const logoutBtn = h('button', { class: 'btn ghost', onclick: logout }, icon('logout', 19), h('span', { class: 'lbl' }, 'Sign out'));
  const sidebar = h('aside', { class: 'sidebar', id: 'sidebar', 'aria-label': 'Main navigation' },
    h('div', { class: 'brand' }, h('div', { class: 'brand-mark' }, 'N'), h('div', { class: 'brand-t' }, h('b', {}, 'NEXORA'), h('span', {}, 'Recap Studio'))),
    h('nav', { class: 'nav' }, ROUTES.map(navLink)), h('div', { class: 'side-foot' }, collapse, logoutBtn));
  const menuBtn = h('button', { class: 'icon-btn top-only-mobile', 'aria-label': 'Open menu', 'aria-controls': 'sidebar', onclick: () => shell.classList.add('drawer-open') }, icon('menu', 22));
  const topbar = h('header', { class: 'topbar' }, menuBtn, h('div', { class: 'crumb', id: 'crumb' }), h('div', { class: 'spacer' }),
    state.readOnly ? h('span', { class: 'ro-badge', title: 'Viewer role: write actions are disabled' }, icon('eye', 14), 'Read-only') : h('span', { class: 'badge b-gold' }, 'Admin'),
    h('button', { class: 'icon-btn', 'aria-label': 'Sign out', title: 'Sign out', onclick: logout }, icon('logout', 19)));
  const content = h('main', { class: 'content', id: 'content', tabindex: '-1' });
  const bottom = h('nav', { class: 'bottom-nav', 'aria-label': 'Quick navigation' },
    BOTTOM.map((id) => { const r = ROUTES.find((x) => x.id === id); return h('a', { href: `#/${id}`, 'data-route': id }, icon(r.icon, 20), r.label.replace('Video ', '').replace(' Studio', '')); }),
    h('button', { onclick: () => shell.classList.add('drawer-open'), 'aria-label': 'More pages' }, icon('more', 20), 'More'));
  shell = h('div', { class: `shell ${store.get('nx_collapsed') === '1' ? 'collapsed' : ''}` }, sidebar, h('div', { class: 'scrim', onclick: () => shell.classList.remove('drawer-open') }), h('div', { class: 'main' }, topbar, content), bottom);
  clear(app).append(shell);
  shell.addEventListener('keydown', (e) => { if (e.key === 'Escape') shell.classList.remove('drawer-open'); });
}

/* ---------- router ---------- */
function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [path, q = ''] = raw.split('?');
  return { id: path || 'dashboard', params: Object.fromEntries(new URLSearchParams(q)) };
}
function teardownPage() {
  poller?.stopAll(); poller = null;
  try { current?.destroy?.(); } catch (e) { console.error(e); }
  current = null; dirtyFn = null;
}

async function route() {
  if (!shell) return;
  const { id, params } = parseHash();
  const def = ROUTES.find((r) => r.id === id) || ROUTES[0];
  if (dirtyFn && dirtyFn()) {
    const ok = await confirmDialog({ title: 'Discard unsaved changes?', message: 'You have unsaved edits on this page. Leaving will discard them.', confirmText: 'Discard and leave' });
    if (!ok) { history.replaceState(null, '', lastHash || '#/dashboard'); markNav(parseHash().id); return; }
  }
  lastHash = location.hash || `#/${def.id}`;
  const token = ++navToken;
  teardownPage();
  markNav(def.id);
  document.title = `${def.label} · NEXORA Studio`;
  $('#crumb').textContent = def.label;
  const root = $('#content');
  clear(root);
  root.append(h('div', { class: 'skel-wrap' }, h('div', { class: 'skeleton', style: { height: '30px', width: '240px', marginBottom: '18px' } }), h('div', { class: 'skeleton', style: { height: '160px' } })));
  try {
    const mod = await import(`./pages/${def.id}.js`);
    if (token !== navToken) return;
    poller = createPoller();
    clear(root);
    const ctx = { root, params, poll: poller, canWrite: !state.readOnly, navigate: (hash) => { location.hash = hash; }, setDirty: (fn) => { dirtyFn = fn; } };
    current = (await mod.default(ctx)) || null;
    root.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  } catch (e) {
    if (token !== navToken) return;
    console.error(e);
    clear(root).append(h('div', { class: 'banner error', role: 'alert' }, icon('alert'), h('div', {}, `Page failed to load: ${e.message}`)));
  }
}
function markNav(id) {
  $$('[data-route]').forEach((a) => (a.dataset.route === id ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
}

window.addEventListener('hashchange', route);
window.addEventListener('beforeunload', (e) => { if (dirtyFn && dirtyFn()) { e.preventDefault(); e.returnValue = ''; } });
window.addEventListener('unhandledrejection', (e) => {
  const r = e.reason;
  if (r && r.name === 'ApiError') { e.preventDefault(); if (r.status !== 401) toastErr(r); }
});
start();
