// Small helpers shared by page modules (not a route).
import { h, icon } from '../ui.js';

/** Only http(s) URLs may become links. */
export const safeUrl = (u) => (typeof u === 'string' && /^https?:\/\//i.test(u.trim()) ? u.trim() : null);
/** Same-origin paths or http(s) URLs may be used as media sources. */
export const safeMedia = (u) => (typeof u === 'string' && (/^\/(?!\/)/.test(u) || /^https?:\/\//i.test(u)) ? u : null);

export function extLink(url, text) {
  const u = safeUrl(url);
  return u ? h('a', { href: u, target: '_blank', rel: 'noopener noreferrer' }, text ?? u, ' ', icon('external', 12)) : h('span', {}, text ?? '—');
}

export const enc = encodeURIComponent;

/** Plain list of {name,url} sources. */
export function sourceList(sources, emptyText = 'No sources listed.') {
  const list = (sources || []).filter(Boolean);
  if (!list.length) return h('p', { class: 'muted sm' }, emptyText);
  return h('ul', { class: 'stack sm' }, list.map((s) => h('li', {}, typeof s === 'string' ? extLink(s, s) : extLink(s.url, s.name || s.url))));
}

export const countText = (n, one, many) => `${n} ${n === 1 ? one : many || one + 's'}`;
