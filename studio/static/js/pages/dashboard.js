import { api } from '../api.js';
import { h, icon, badge, statusBadge, platformBadge, fmtDateTime, fmtTime, fmtRel, fmtDur, fmtSize, fmtGB, fmtNum, titleCase, act, skeleton, errorState, emptyState } from '../ui.js';
import { pageHead, card, kv, jobCard } from '../comp.js';
import { sparkline, gauge } from '../charts.js';

const hist = { queued: [], running: [], failed: [], done: [] };

function kpi(label, key, tone, jobs) {
  const arr = hist[key];
  return h('div', { class: `card kpi tone-${tone}` }, h('span', { class: 'k-l' }, label), h('span', { class: 'k-v' }, fmtNum(jobs[key] ?? 0)),
    sparkline(arr.length > 1 ? arr : [jobs[key] || 0, jobs[key] || 0], { color: `var(--${tone === 'blue' ? 'blue' : tone === 'ok' ? 'ok' : tone === 'err' ? 'err' : 'gold'})`, label: `${label} trend (this session)` }));
}

function providerRow(p) {
  return h('div', { class: 'list-item' },
    h('span', { class: `dot ${p.configured ? (p.last_error && (!p.last_ok || p.last_error_at > p.last_ok) ? 'warn' : 'ok') : 'err'}` }),
    h('div', { class: 'grow' }, h('b', {}, p.id === 'openai' ? 'OpenAI' : 'Gemini'), h('span', { class: 'muted sm' }, `${p.model || 'no model'} · ${p.calls} calls · ${p.failures} failures`),
      p.last_error ? h('p', { class: 'txt-err sm' }, `Last error ${fmtRel(p.last_error_at)}: ${p.last_error}`) : p.last_ok ? h('p', { class: 'muted sm' }, `Last OK ${fmtRel(p.last_ok)}`) : null),
    h('div', { class: 'row' }, p.primary ? badge('Primary', 'gold') : null, badge(p.configured ? 'Configured' : 'Not configured', p.configured ? 'ok' : 'err')));
}

function render(d, ctx, reload) {
  const r = d.resources || {}, a = d.automation || {}, t = d.telegram || {};
  const diskUsed = r.disk_total_gb ? ((r.disk_total_gb - r.disk_free_gb) / r.disk_total_gb) * 100 : null;
  const memNote = r.mem_free_mb == null ? 'n/a' : `${fmtNum(Math.round(r.mem_free_mb))} MB free`;
  const out = h('div', { class: 'stack' });
  if (d.alerts?.length) out.append(h('div', { class: 'stack sm', role: 'region', 'aria-label': 'Alerts' }, d.alerts.map((al) => h('div', { class: `banner ${al.level === 'error' ? 'error' : al.level === 'warn' ? 'warn' : 'info'}` }, icon(al.level === 'info' ? 'info' : 'alert'), h('div', {}, al.msg, ' ', h('span', { class: 'mono faint' }, al.code))))));
  out.append(h('div', { class: 'grid cols-4 kpis' }, kpi('Queued', 'queued', 'gold', d.jobs), kpi('Running', 'running', 'blue', d.jobs), kpi('Failed', 'failed', 'err', d.jobs), kpi('Done', 'done', 'ok', d.jobs)));

  out.append(h('div', { class: 'grid cols-3' },
    card('System health', h('div', {},
      kv('Backend', h('span', {}, h('span', { class: `dot ${d.backend?.ok ? 'ok' : 'err'}` }), d.backend?.ok ? 'Healthy' : 'Down')),
      kv('Version', d.backend?.version), kv('Uptime', fmtDur(d.backend?.uptime_s)),
      kv('Studio workers', badge(d.backend?.studio_workers ? 'Running' : 'Stopped', d.backend?.studio_workers ? 'ok' : 'err')), kv('DB schema', d.backend?.db_schema)),
    { actions: h('span', { class: 'muted sm' }, `Updated ${fmtTime(d.now)}`) }),
    card('Telegram', h('div', {},
      kv('Status', t.configured ? badge(t.connected ? 'Connected' : 'Disconnected', t.connected ? 'ok' : 'err') : badge('Not configured', 'warn')),
      kv('Bot', t.bot_username ? '@' + t.bot_username : '—'), kv('Chat', badge(t.chat_configured ? 'Configured' : 'Missing', t.chat_configured ? 'ok' : 'warn')),
      kv('Pending updates', t.pending_updates ?? '—'), t.error ? h('p', { class: 'txt-err sm pad' }, t.error) : null)),
    card('AI providers', h('div', {}, (d.providers || []).map(providerRow)), { actions: h('a', { class: 'btn sm ghost', href: '#/settings' }, 'Configure') })));

  const pickList = a.today?.picks?.length ? h('div', { class: 'stack sm' }, a.today.picks.map((p) => h('div', { class: 'pick' }, h('div', { class: 'row between' }, platformBadge(p.platform), badge(p.category, 'muted')),
    h('b', {}, p.title), p.project_id ? h('a', { class: 'sm', href: `#/renderer?project=${p.project_id}` }, `Project #${p.project_id} →`) : h('span', { class: 'muted sm' }, 'Project not created yet'))))
    : emptyState({ icon: 'star', title: 'No picks for today', text: 'Picks appear once automation selects three titles.' });
  out.append(h('div', { class: 'grid split' },
    card('Automation', h('div', { class: 'stack' }, h('div', { class: 'grid cols-3 keep2' }, h('div', {}, h('p', { class: 'lbl-s' }, 'State'), statusBadge(a.state === 'running' ? 'running' : a.state)),
      h('div', {}, h('p', { class: 'lbl-s' }, 'Schedule'), h('b', {}, `${a.schedule || '—'} ICT`)), h('div', {}, h('p', { class: 'lbl-s' }, 'Next run'), h('b', {}, fmtDateTime(a.next_run)))),
    h('p', { class: 'lbl-s' }, `Today's three picks${a.today?.date ? ' · ' + a.today.date : ''}`), pickList), { actions: h('a', { class: 'btn sm ghost', href: '#/automation' }, 'Manage') }),
    card('Resources', h('div', { class: 'stack' },
      gauge(diskUsed, { label: 'Disk', value: `${fmtGB(r.disk_free_gb)} free of ${fmtGB(r.disk_total_gb)}` }),
      gauge(null, { label: 'Memory', value: memNote }),
      h('div', { class: 'gauge' }, h('div', { class: 'row' }, badge(`ffmpeg ${r.ffmpeg ? 'available' : 'missing'}`, r.ffmpeg ? 'ok' : 'err'), badge(`GPU ${r.gpu ? 'available' : 'not available'}`, r.gpu ? 'ok' : 'muted'), badge(`${r.cpu_count ?? '?'} CPU`, 'muted'))),
      kv('Data directory', fmtGB(r.data_dir_gb))))));

  out.append(card('Running jobs', d.running_jobs?.length ? h('div', { class: 'job-grid' }, d.running_jobs.map((j) => jobCard(j, { onOpen: () => ctx.navigate(`#/renderer?project=${j.project_id}`) })))
    : emptyState({ icon: 'video', title: 'No jobs running', text: 'Start a recap in Recap Studio or let Automation run on schedule.', action: h('a', { class: 'btn primary', href: '#/recap-studio' }, 'Open Recap Studio') }),
    { actions: h('a', { class: 'btn sm ghost', href: '#/renderer' }, 'Render queue') }));

  out.append(h('div', { class: 'grid cols-3' },
    card('Recent projects', d.recent_projects?.length ? h('div', {}, d.recent_projects.map((p) => h('a', { class: 'list-item', href: `#/projects?project=${p.id}`, style: { color: 'inherit', textDecoration: 'none' } },
      h('div', { class: 'grow' }, h('b', {}, p.title), h('span', { class: 'muted sm' }, `${p.date} · ${p.category || '—'}`)), platformBadge(p.platform), statusBadge(p.status)))) : emptyState({ icon: 'folder', title: 'No projects yet' })),
    card('Recent videos', d.recent_videos?.length ? h('div', {}, d.recent_videos.map((v) => h('div', { class: 'list-item' }, h('div', { class: 'grow' }, h('b', {}, v.title), h('span', { class: 'muted sm' }, `${fmtSize(v.size)} · ${fmtDur(v.duration)} · ${fmtRel(v.created)}`)), platformBadge(v.platform),
      h('a', { class: 'btn sm', href: `/api/files/${v.file_id}/download`, 'aria-label': `Download ${v.title}` }, icon('download', 14))))) : emptyState({ icon: 'video', title: 'No finished videos yet' })),
    card('Recent errors', d.recent_errors?.length ? h('div', {}, d.recent_errors.map((e) => h('div', { class: 'list-item' }, h('div', { class: 'grow' }, h('b', { class: 'txt-err' }, e.msg), h('span', { class: 'muted sm' }, `${fmtDateTime(e.ts)} · ${e.stage || '—'} · job #${e.job_id ?? '—'}`)), e.platform ? platformBadge(e.platform) : null)))
      : h('p', { class: 'muted pad' }, 'No recent errors.'))));
  return out;
}

export default async function page(ctx) {
  ctx.root.append(pageHead('Dashboard', 'Live overview of the recap pipeline. Refreshes every 5 seconds while this tab is visible.'));
  const box = h('div', {}, skeleton('cards', 4));
  ctx.root.append(box);
  let sig = '', first = true, alive = true;
  async function load() {
    try {
      const d = await api.get('/api/dashboard');
      if (!alive) return;
      for (const k of Object.keys(hist)) { hist[k].push(d.jobs?.[k] ?? 0); if (hist[k].length > 40) hist[k].shift(); }
      const s = JSON.stringify({ ...d, now: 0, backend: { ...d.backend, uptime_s: 0 } });
      if (s === sig) return;
      sig = s; first = false;
      box.replaceChildren(render(d, ctx, load));
    } catch (e) {
      if (!alive || e.status === 401) return;
      if (first) box.replaceChildren(errorState(e, () => { box.replaceChildren(skeleton('cards', 4)); load(); }));
    }
  }
  await load();
  ctx.poll.add(load, 5000);
  return { destroy() { alive = false; } };
}
