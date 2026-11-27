// Core UI helpers: DOM builder (XSS-safe), toasts, dialogs, drawers, states, formatters, polling.
import { iconSvg } from './icons.js';

export const state = { readOnly: false, role: null };
export const TZ = 'Asia/Bangkok';

/* ---------- DOM helper (never uses innerHTML with data) ---------- */
const PROP_KEYS = new Set(['value', 'checked', 'disabled', 'selected', 'indeterminate', 'multiple', 'readOnly', 'open']);

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function append(el, kids) {
  for (const k of kids) {
    if (k == null || k === false || k === true) continue;
    if (Array.isArray(k)) append(el, k);
    else if (k instanceof Node) el.appendChild(k);
    else el.appendChild(document.createTextNode(String(k)));
  }
}

export function h(tag, props, ...kids) {
  if (props != null && (typeof props !== 'object' || props instanceof Node || Array.isArray(props))) {
    kids.unshift(props);
    props = null;
  }
  const el = document.createElement(tag);
  let late = null;
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'write') {
      if (state.readOnly) { el.disabled = true; el.title = 'Read-only: viewer role cannot change data'; el.setAttribute('aria-disabled', 'true'); }
    } else if (PROP_KEYS.has(k)) (late ||= []).push([k, v]);
    else el.setAttribute(k, v === true ? '' : String(v));
  }
  append(el, kids);
  if (late) for (const [k, v] of late) el[k] = v;
  return el;
}

export function icon(name, size = 18) {
  const s = document.createElement('span');
  s.className = 'ic-wrap';
  s.innerHTML = iconSvg(name, size); // static constant markup only
  return s;
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const clear = (el) => { el.replaceChildren(); return el; };
export function debounce(fn, ms = 250) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

/* ---------- formatters ---------- */
const dtf = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
const tf = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const df = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, year: 'numeric', month: 'short', day: '2-digit' });
const okTs = (t) => t != null && isFinite(t) && t > 0;
export const fmtDateTime = (t) => (okTs(t) ? dtf.format(new Date(t * 1000)) + ' ICT' : '—');
export const fmtTime = (t) => (okTs(t) ? tf.format(new Date(t * 1000)) : '—');
export const fmtDate = (t) => (okTs(t) ? df.format(new Date(t * 1000)) : '—');
export function fmtRel(t) {
  if (!okTs(t)) return '—';
  const d = Date.now() / 1000 - t, a = Math.abs(d);
  const u = a < 60 ? [Math.round(a), 's'] : a < 3600 ? [Math.round(a / 60), 'm'] : a < 86400 ? [Math.round(a / 3600), 'h'] : [Math.round(a / 86400), 'd'];
  return d >= 0 ? `${u[0]}${u[1]} ago` : `in ${u[0]}${u[1]}`;
}
export function fmtDur(sec) {
  if (sec == null || !isFinite(sec)) return '—';
  sec = Math.max(0, Math.round(sec));
  const hh = Math.floor(sec / 3600), mm = Math.floor((sec % 3600) / 60), ss = sec % 60;
  return `${hh}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
}
export function fmtSize(b) {
  if (b == null || !isFinite(b)) return '—';
  if (b >= 1024 ** 3) return (b / 1024 ** 3).toFixed(2) + ' GB';
  return (b / 1024 ** 2).toFixed(b < 1024 ** 2 / 10 ? 2 : 1) + ' MB';
}
export const fmtGB = (g) => (g == null ? '—' : Number(g).toFixed(1) + ' GB');
export const fmtNum = (n) => (n == null ? '—' : new Intl.NumberFormat('en-US').format(n));
/** seconds -> mm:ss.mmm */
export function fmtClock(sec) {
  sec = Math.max(0, Number(sec) || 0);
  const m = Math.floor(sec / 60), s = sec - m * 60;
  return `${String(m).padStart(2, '0')}:${s.toFixed(3).padStart(6, '0')}`;
}
/** mm:ss.mmm (or hh:mm:ss.mmm / plain seconds) -> seconds, NaN if invalid */
export function parseClock(str) {
  const parts = String(str).trim().split(':');
  if (parts.length > 3 || !parts.length) return NaN;
  let total = 0;
  for (const p of parts) { if (!/^\d+(\.\d+)?$/.test(p)) return NaN; total = total * 60 + parseFloat(p); }
  return total;
}
export const clamp = (n, a, b) => Math.min(b, Math.max(a, n));
export const titleCase = (s) => String(s || '').replace(/[_-]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export const PLATFORMS = ['youtube', 'facebook', 'tiktok'];
export const PLATFORM_LABEL = { youtube: 'YouTube', facebook: 'Facebook', tiktok: 'TikTok' };
export const STAGES = ['research', 'script', 'voice', 'srt', 'assets', 'timeline', 'render', 'qc', 'publish', 'notify'];
export const CATEGORIES = ['Anime', 'Donghua', 'Cartoon', '3D Animation', 'International Movies'];
export const FORMATS = { landscape_16_9: 'Landscape 16:9', vertical_9_16: 'Vertical 9:16', square_1_1: 'Square 1:1', portrait_4_5: 'Portrait 4:5' };
export const RESOLUTIONS = ['720p', '1080p', '1440p', '2160p'];

/* ---------- toasts ---------- */
let toastBox;
export function toast(msg, type = 'info', ms) {
  if (!toastBox) {
    toastBox = h('div', { class: 'toasts', role: 'status', 'aria-live': 'polite', 'aria-atomic': 'false' });
    document.body.appendChild(toastBox);
  }
  const ic = { ok: 'check', err: 'alert', warn: 'alert', info: 'info' }[type] || 'info';
  const t = h('div', { class: `toast t-${type}`, role: type === 'err' ? 'alert' : null }, icon(ic, 18), h('div', { class: 'toast-msg' }, msg),
    h('button', { class: 'icon-btn sm', 'aria-label': 'Dismiss', onclick: () => t.remove() }, icon('x', 14)));
  toastBox.appendChild(t);
  while (toastBox.children.length > 5) toastBox.firstChild.remove();
  setTimeout(() => t.remove(), ms || (type === 'err' ? 8000 : 4200));
}
export const toastOk = (m) => toast(m, 'ok');
export const toastErr = (e) => toast(e?.message || String(e), 'err');

/** Run an async action with button lock + success/error toasts. Returns result or undefined on failure. */
export async function act(fn, { ok, btn } = {}) {
  if (btn) btn.disabled = true;
  try {
    const r = await fn();
    if (ok) toast(typeof ok === 'function' ? ok(r) : ok, 'ok');
    return r;
  } catch (e) {
    if (e?.status !== 401) toastErr(e);
    return undefined;
  } finally {
    if (btn && btn.isConnected && !state.readOnly) btn.disabled = false;
  }
}

/* ---------- overlays: modal + drawer with focus trap ---------- */
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
function overlay(kind, { title, body, actions, onClose, wide }) {
  const prev = document.activeElement;
  const tid = 'ov' + Math.random().toString(36).slice(2, 8);
  const closeBtn = h('button', { class: 'icon-btn', 'aria-label': 'Close', onclick: () => close() }, icon('x'));
  const bodyEl = h('div', { class: `${kind}-body` }, body);
  const panel = h('div', { class: `${kind} ${wide ? 'wide' : ''}`, role: kind === 'modal' ? 'dialog' : 'dialog', 'aria-modal': 'true', 'aria-labelledby': tid, tabindex: '-1' },
    h('div', { class: `${kind}-head` }, h('h2', { id: tid }, title), closeBtn), bodyEl,
    actions ? h('div', { class: `${kind}-foot` }, actions) : null);
  const back = h('div', { class: `backdrop ${kind}-back` }, panel);
  back.addEventListener('mousedown', (e) => { if (e.target === back) close(); });
  function onKey(e) {
    if (e.key === 'Escape') { e.stopPropagation(); close(); return; }
    if (e.key !== 'Tab') return;
    const f = $$(FOCUSABLE, panel).filter((x) => x.offsetParent !== null);
    if (!f.length) { e.preventDefault(); return; }
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === panel)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  let closed = false;
  function close(result) {
    if (closed) return; closed = true;
    document.removeEventListener('keydown', onKey, true);
    back.classList.add('leaving');
    setTimeout(() => back.remove(), 160);
    if (document.querySelectorAll('.backdrop:not(.leaving)').length === 0) document.body.classList.remove('no-scroll');
    prev && prev.focus && prev.isConnected && prev.focus();
    onClose && onClose(result);
  }
  document.addEventListener('keydown', onKey, true);
  document.body.appendChild(back);
  document.body.classList.add('no-scroll');
  requestAnimationFrame(() => {
    back.classList.add('shown');
    const auto = $('[autofocus],[data-autofocus]', panel) || $$(FOCUSABLE, panel).find((x) => x !== closeBtn) || closeBtn;
    auto.focus();
  });
  return { el: panel, body: bodyEl, close, set title(t) { $('h2', panel).textContent = t; } };
}
export const modal = (o) => overlay('modal', o);
export const drawer = (o) => overlay('drawer', o);

/** Confirm dialog spelling out what will happen. Resolves true/false. */
export function confirmDialog({ title, message, items = [], confirmText = 'Confirm', danger = true }) {
  return new Promise((resolve) => {
    let done = false;
    const finish = (v) => { if (!done) { done = true; resolve(v); } };
    const okBtn = h('button', { class: `btn ${danger ? 'danger' : 'primary'}`, 'data-autofocus': '', onclick: () => { finish(true); m.close(); } }, confirmText);
    const m = modal({
      title,
      body: [h('p', { class: 'confirm-msg' }, message), items.length ? h('ul', { class: 'confirm-list' }, items.map((i) => h('li', {}, i))) : null],
      actions: [h('button', { class: 'btn ghost', onclick: () => { finish(false); m.close(); } }, 'Cancel'), okBtn],
      onClose: () => finish(false),
    });
  });
}

/* ---------- states ---------- */
export function skeleton(kind = 'rows', n = 3) {
  if (kind === 'cards') return h('div', { class: 'grid cols-3 skel-wrap', 'aria-busy': 'true', 'aria-label': 'Loading' }, Array.from({ length: n }, () => h('div', { class: 'card skel-card' }, h('div', { class: 'skeleton', style: { width: '40%', height: '14px' } }), h('div', { class: 'skeleton', style: { width: '70%', height: '28px', marginTop: '14px' } }), h('div', { class: 'skeleton', style: { width: '100%', height: '44px', marginTop: '14px' } }))));
  return h('div', { class: 'skel-wrap', 'aria-busy': 'true', 'aria-label': 'Loading' }, Array.from({ length: n }, (_, i) => h('div', { class: 'skeleton', style: { height: '18px', width: `${95 - (i % 3) * 18}%`, marginBottom: '12px' } })));
}
export function emptyState({ icon: ic = 'info', title, text, action }) {
  return h('div', { class: 'empty' }, h('div', { class: 'empty-ic' }, icon(ic, 26)), h('h3', {}, title), text ? h('p', {}, text) : null, action || null);
}
export function errorState(err, retry) {
  return h('div', { class: 'empty err-state', role: 'alert' }, h('div', { class: 'empty-ic bad' }, icon('alert', 26)), h('h3', {}, 'Could not load this view'),
    h('p', {}, err?.message || 'Unknown error'), err?.code ? h('p', { class: 'mono faint' }, `code: ${err.code}`) : null,
    retry ? h('button', { class: 'btn', onclick: retry }, icon('refresh', 16), 'Retry') : null);
}

/** Shows skeleton, runs loader, renders result into box; error state with Retry. */
export async function loadView(box, loader, render, { skel = 'rows', n = 3 } = {}) {
  box.replaceChildren(skeleton(skel, n));
  try {
    const data = await loader();
    if (!box.isConnected) return;
    box.replaceChildren();
    append(box, [render(data)]);
    return data;
  } catch (e) {
    if (!box.isConnected || e?.status === 401) return;
    box.replaceChildren(errorState(e, () => loadView(box, loader, render, { skel, n })));
  }
}

/* ---------- polling with cleanup ---------- */
export function createPoller() {
  const stops = new Set();
  return {
    add(fn, ms = 5000, { immediate = false } = {}) {
      let busy = false, dead = false;
      const tick = async () => {
        if (dead || busy || document.hidden) return;
        busy = true;
        try { await fn(); } catch { /* handled by caller */ }
        busy = false;
      };
      const iv = setInterval(tick, ms);
      const vis = () => { if (!document.hidden) tick(); };
      document.addEventListener('visibilitychange', vis);
      if (immediate) tick();
      const stop = () => { dead = true; clearInterval(iv); document.removeEventListener('visibilitychange', vis); stops.delete(stop); };
      stops.add(stop);
      return stop;
    },
    stopAll() { [...stops].forEach((s) => s()); },
  };
}

/* ---------- tone helpers ---------- */
const TONES = {
  completed: 'ok', done: 'ok', published: 'ok', verified: 'ok', ready_to_publish: 'ok', draft_ready: 'ok', uploaded: 'ok', running: 'blue', queued: 'muted', paused: 'warn', draft: 'muted',
  failed: 'err', cancelled: 'muted', not_ready: 'warn', unavailable: 'muted', partial: 'warn', insufficient_sources: 'warn', not_found: 'err', excluded: 'err',
};
export const toneOf = (s) => TONES[s] || 'muted';
export const badge = (text, tone = 'muted', title) => h('span', { class: `badge b-${tone}`, title }, text);
export const statusBadge = (s) => badge(titleCase(s || 'unknown'), toneOf(s));
export const platformBadge = (p) => h('span', { class: `badge plat p-${p}` }, PLATFORM_LABEL[p] || p);
export function progressBar(pct, tone = 'gold') {
  const v = clamp(Number(pct) || 0, 0, 100);
  return h('div', { class: `progress ${tone}`, role: 'progressbar', 'aria-valuenow': Math.round(v), 'aria-valuemin': 0, 'aria-valuemax': 100 }, h('span', { style: { width: v + '%' } }));
}

export function downloadUrl(file, inline) { return file.download_url + (inline ? (file.download_url.includes('?') ? '&' : '?') + 'inline=1' : ''); }
