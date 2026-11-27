// Hand-drawn SVG charts (no libraries). All colours come from CSS variables.
import { h } from './ui.js';

const NS = 'http://www.w3.org/2000/svg';
export function sv(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else el.setAttribute(k, String(v));
  }
  for (const k of kids.flat()) if (k != null) el.appendChild(typeof k === 'string' ? document.createTextNode(k) : k);
  return el;
}
const title = (t) => sv('title', {}, t);
export const PALETTE = ['var(--gold)', 'var(--blue)', 'var(--ok)', 'var(--violet)', 'var(--warn)', 'var(--err)'];
const nice = (max) => { if (max <= 5) return 5; const p = 10 ** Math.floor(Math.log10(max)); return Math.ceil(max / p) * p; };

export function sparkline(values, { w = 120, h: hh = 36, color = 'var(--gold)', label = 'trend' } = {}) {
  const v = values && values.length > 1 ? values : [0, 0];
  const max = Math.max(...v, 1), min = Math.min(...v, 0);
  const x = (i) => (i / (v.length - 1)) * (w - 4) + 2;
  const y = (n) => hh - 3 - ((n - min) / (max - min || 1)) * (hh - 8);
  const pts = v.map((n, i) => `${x(i).toFixed(1)},${y(n).toFixed(1)}`);
  const gid = 'sg' + Math.random().toString(36).slice(2, 7);
  return sv('svg', { class: 'spark', viewBox: `0 0 ${w} ${hh}`, preserveAspectRatio: 'none', role: 'img', 'aria-label': label },
    sv('defs', {}, sv('linearGradient', { id: gid, x1: 0, y1: 0, x2: 0, y2: 1 }, sv('stop', { offset: '0%', 'stop-color': color, 'stop-opacity': '.35' }), sv('stop', { offset: '100%', 'stop-color': color, 'stop-opacity': '0' }))),
    sv('polygon', { points: `2,${hh} ${pts.join(' ')} ${w - 2},${hh}`, fill: `url(#${gid})` }),
    sv('polyline', { points: pts.join(' '), fill: 'none', stroke: color, 'stroke-width': 1.8, 'stroke-linejoin': 'round', 'stroke-linecap': 'round', 'vector-effect': 'non-scaling-stroke' }));
}

export function miniBars(values, { w = 120, h: hh = 36, color = 'var(--gold)', label = 'bars' } = {}) {
  const v = values && values.length ? values : [0];
  const max = Math.max(...v, 1), bw = w / v.length;
  return sv('svg', { class: 'spark', viewBox: `0 0 ${w} ${hh}`, preserveAspectRatio: 'none', role: 'img', 'aria-label': label },
    v.map((n, i) => sv('rect', { x: i * bw + 1, y: hh - Math.max(2, (n / max) * (hh - 2)), width: Math.max(1, bw - 2), height: Math.max(2, (n / max) * (hh - 2)), rx: 1.5, fill: color, opacity: n ? 0.9 : 0.25 })));
}

/** grouped vertical bars: data=[{label, a, b}] ; series=[{key,label,color}] */
export function groupedBars(data, series, { height = 220 } = {}) {
  const W = 720, H = height, pl = 34, pb = 24, pt = 10, pr = 6;
  const max = nice(Math.max(1, ...data.flatMap((d) => series.map((s) => d[s.key] || 0))));
  const iw = W - pl - pr, ih = H - pt - pb, slot = iw / Math.max(1, data.length);
  const bw = Math.max(2, Math.min(18, (slot - 3) / series.length));
  const svg = sv('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': series.map((s) => s.label).join(' vs ') + ' per day' });
  for (let i = 0; i <= 4; i++) {
    const y = pt + ih - (ih * i) / 4;
    svg.append(sv('line', { x1: pl, x2: W - pr, y1: y, y2: y, class: 'grid-l' }), sv('text', { x: pl - 6, y: y + 3, class: 'ax', 'text-anchor': 'end' }, String(Math.round((max * i) / 4))));
  }
  const every = Math.ceil(data.length / 10);
  data.forEach((d, i) => {
    const cx = pl + slot * i + slot / 2;
    series.forEach((s, j) => {
      const val = d[s.key] || 0, bh = (val / max) * ih;
      svg.append(sv('rect', { x: cx - (bw * series.length) / 2 + j * bw, y: pt + ih - bh, width: bw - 1, height: Math.max(bh, val ? 1.5 : 0), rx: 2, fill: s.color }, title(`${d.label}: ${s.label} ${val}`)));
    });
    if (i % every === 0) svg.append(sv('text', { x: cx, y: H - 6, class: 'ax', 'text-anchor': 'middle' }, d.label.slice(5)));
  });
  return svg;
}

export function lineChart(points, { height = 200, color = 'var(--gold)', label = 'line' } = {}) {
  const W = 720, H = height, pl = 34, pb = 24, pt = 12, pr = 10;
  const max = nice(Math.max(1, ...points.map((p) => p.y)));
  const iw = W - pl - pr, ih = H - pt - pb;
  const x = (i) => pl + (points.length > 1 ? (i / (points.length - 1)) * iw : iw / 2), y = (v) => pt + ih - (v / max) * ih;
  const svg = sv('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': label });
  for (let i = 0; i <= 4; i++) {
    const yy = pt + ih - (ih * i) / 4;
    svg.append(sv('line', { x1: pl, x2: W - pr, y1: yy, y2: yy, class: 'grid-l' }), sv('text', { x: pl - 6, y: yy + 3, class: 'ax', 'text-anchor': 'end' }, String(Math.round((max * i) / 4))));
  }
  const pts = points.map((p, i) => `${x(i).toFixed(1)},${y(p.y).toFixed(1)}`);
  const gid = 'lg' + Math.random().toString(36).slice(2, 7);
  svg.append(sv('defs', {}, sv('linearGradient', { id: gid, x1: 0, y1: 0, x2: 0, y2: 1 }, sv('stop', { offset: '0%', 'stop-color': color, 'stop-opacity': '.3' }), sv('stop', { offset: '100%', 'stop-color': color, 'stop-opacity': 0 }))),
    sv('polygon', { points: `${x(0)},${pt + ih} ${pts.join(' ')} ${x(points.length - 1)},${pt + ih}`, fill: `url(#${gid})` }),
    sv('polyline', { points: pts.join(' '), fill: 'none', stroke: color, 'stroke-width': 2.2, 'stroke-linejoin': 'round' }));
  const every = Math.ceil(points.length / 10);
  points.forEach((p, i) => {
    svg.append(sv('circle', { cx: x(i), cy: y(p.y), r: 3, fill: color }, title(`${p.x}: ${p.y}`)));
    if (i % every === 0) svg.append(sv('text', { x: x(i), y: H - 6, class: 'ax', 'text-anchor': 'middle' }, p.x.slice(5)));
  });
  return svg;
}

/** donut with legend. items=[{label,value,color?}] */
export function donut(items, { size = 170, center = '', sub = '' } = {}) {
  const tot = items.reduce((a, b) => a + b.value, 0);
  const r = 62, c = 2 * Math.PI * r;
  const svg = sv('svg', { class: 'donut', viewBox: '0 0 160 160', width: size, height: size, role: 'img', 'aria-label': 'distribution chart' },
    sv('circle', { cx: 80, cy: 80, r, fill: 'none', stroke: 'var(--panel3)', 'stroke-width': 18 }));
  let off = 0;
  items.forEach((it, i) => {
    if (!it.value || !tot) return;
    const len = (it.value / tot) * c;
    svg.append(sv('circle', { cx: 80, cy: 80, r, fill: 'none', stroke: it.color || PALETTE[i % PALETTE.length], 'stroke-width': 18, 'stroke-dasharray': `${Math.max(0, len - 1.5)} ${c - len + 1.5}`, 'stroke-dashoffset': -off, transform: 'rotate(-90 80 80)' }, title(`${it.label}: ${it.value}`)));
    off += len;
  });
  svg.append(sv('text', { x: 80, y: 82, class: 'donut-n', 'text-anchor': 'middle' }, String(center)), sv('text', { x: 80, y: 100, class: 'donut-s', 'text-anchor': 'middle' }, sub));
  const legend = h('ul', { class: 'legend' }, items.map((it, i) => h('li', {}, h('i', { style: { background: it.color || PALETTE[i % PALETTE.length] } }), h('span', {}, it.label), h('b', {}, String(it.value)))));
  return h('div', { class: 'donut-wrap' }, svg, legend);
}

/** horizontal bars as HTML */
export function hbars(items, { color = 'var(--gold)', fmt = (v) => v } = {}) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return h('ul', { class: 'hbars' }, items.map((it) => h('li', {}, h('span', { class: 'hb-l' }, it.label), h('span', { class: 'hb-t' }, h('i', { style: { width: (it.value / max) * 100 + '%', background: it.color || color } })), h('b', {}, String(fmt(it.value))))));
}

/** ring gauge */
export function gauge(pct, { label, value, tone } = {}) {
  const p = Math.max(0, Math.min(100, pct ?? 0)), r = 26, c = 2 * Math.PI * r;
  const col = tone || (p > 90 ? 'var(--err)' : p > 75 ? 'var(--warn)' : 'var(--gold)');
  return h('div', { class: 'gauge' },
    sv('svg', { viewBox: '0 0 64 64', width: 64, height: 64, role: 'img', 'aria-label': `${label} ${Math.round(p)}%` },
      sv('circle', { cx: 32, cy: 32, r, fill: 'none', stroke: 'var(--panel3)', 'stroke-width': 7 }),
      sv('circle', { cx: 32, cy: 32, r, fill: 'none', stroke: col, 'stroke-width': 7, 'stroke-linecap': 'round', 'stroke-dasharray': `${(p / 100) * c} ${c}`, transform: 'rotate(-90 32 32)' }),
      sv('text', { x: 32, y: 36, class: 'g-t', 'text-anchor': 'middle' }, pct == null ? '—' : Math.round(p) + '%')),
    h('div', {}, h('b', {}, label), h('span', { class: 'muted' }, value)));
}
