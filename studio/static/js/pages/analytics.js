import { api } from '../api.js';
import { h, icon, badge, platformBadge, loadView, emptyState, fmtNum, fmtDur, PLATFORMS, PLATFORM_LABEL } from '../ui.js';
import { pageHead, card, kv, dataTable } from '../comp.js';
import { groupedBars, donut, hbars } from '../charts.js';

const RANGES = [7, 14, 30, 90];
const PLAT_COLOR = { youtube: '#ff7b7b', facebook: '#6ea4ff', tiktok: '#4de6dc' };

export default async function page(ctx) {
  let days = 30;
  const box = h('div');
  const sel = h('select', { id: 'days', 'aria-label': 'Date range', onchange: (e) => { days = +e.target.value; load(); } }, RANGES.map((d) => h('option', { value: d, selected: d === days }, `Last ${d} days`)));
  ctx.root.append(pageHead('Analytics', 'Production results from real pipeline history.', h('div', { class: 'row' }, sel, h('button', { class: 'btn', onclick: () => load() }, icon('refresh', 16), 'Refresh'))), box);

  const stat = (label, value, tone = 'gold') => h('div', { class: `card kpi tone-${tone}` }, h('span', { class: 'k-l' }, label), h('span', { class: 'k-v' }, value));

  function load() {
    return loadView(box, () => api.get('/api/analytics', { days }), (d) => {
      const t = d.totals || {}, daily = d.days || [];
      const done = daily.reduce((a, x) => a + (x.completed || 0), 0), failed = daily.reduce((a, x) => a + (x.failed || 0), 0);
      const plat = d.by_platform || {}, cats = Object.entries(d.by_category || {}), reasons = d.failure_reasons || [];
      const anyData = done + failed > 0 || (t.projects || 0) > 0;
      const out = h('div', { class: 'stack' });
      out.append(h('div', { class: 'grid cols-4 kpis' }, stat('Projects', fmtNum(t.projects ?? 0)), stat('Videos', fmtNum(t.videos ?? 0), 'blue'), stat('Minutes produced', fmtNum(Math.round(t.minutes_produced ?? 0)), 'ok'), stat('Storage used', t.storage_mb != null ? `${fmtNum(Math.round(t.storage_mb))} MB` : '—')));
      if (!anyData) { out.append(card(null, emptyState({ icon: 'chart', title: 'No production data yet', text: `Nothing was completed or failed in the last ${days} days. Charts fill in as recaps are produced.` }))); return out; }

      out.append(card('Completed vs failed per day', h('div', { class: 'stack sm' },
        h('div', { class: 'legend-inline' }, h('span', {}, h('i', { style: { background: 'var(--ok)' } }), `Completed (${fmtNum(done)})`), h('span', {}, h('i', { style: { background: 'var(--err)' } }), `Failed (${fmtNum(failed)})`)),
        daily.length ? groupedBars(daily.map((x) => ({ label: x.date, completed: x.completed || 0, failed: x.failed || 0 })), [{ key: 'completed', label: 'Completed', color: 'var(--ok)' }, { key: 'failed', label: 'Failed', color: 'var(--err)' }]) : h('p', { class: 'muted' }, 'No daily data.'))));

      out.append(h('div', { class: 'grid cols-2' },
        card('By platform', h('div', { class: 'stack' },
          donut(PLATFORMS.map((p) => ({ label: PLATFORM_LABEL[p], value: plat[p]?.completed || 0, color: PLAT_COLOR[p] })), { center: String(PLATFORMS.reduce((a, p) => a + (plat[p]?.completed || 0), 0)), sub: 'completed' }),
          dataTable([{ label: 'Platform', render: (r) => platformBadge(r.p) }, { label: 'Completed', render: (r) => fmtNum(r.completed ?? 0) }, { label: 'Failed', render: (r) => fmtNum(r.failed ?? 0) }, { label: 'Avg minutes', render: (r) => (r.avg_minutes != null ? Number(r.avg_minutes).toFixed(1) : '—') }],
            PLATFORMS.map((p) => ({ p, ...(plat[p] || {}) }))))),
        card('By category', cats.some(([, n]) => n) ? hbars(cats.map(([k, n]) => ({ label: k, value: n })), { color: 'var(--blue)' }) : emptyState({ icon: 'chart', title: 'No category data' }))));

      out.append(h('div', { class: 'grid cols-2' },
        card('Failure reasons', reasons.length ? hbars(reasons.map((r) => ({ label: r.reason, value: r.count })), { color: 'var(--err)' }) : emptyState({ icon: 'check', title: 'No failures recorded', text: 'Nothing failed in this period.' })),
        card('Durations', h('div', {}, kv('Average render time', d.durations?.avg_render_s != null ? fmtDur(d.durations.avg_render_s) : '—'), kv('Average total time per project', d.durations?.avg_total_s != null ? fmtDur(d.durations.avg_total_s) : '—'), kv('Period', `${days} days`)))));
      return out;
    }, { skel: 'cards', n: 4 });
  }
  await load();
  return {};
}
