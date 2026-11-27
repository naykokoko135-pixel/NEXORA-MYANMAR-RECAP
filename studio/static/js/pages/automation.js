import { api } from '../api.js';
import { h, icon, badge, statusBadge, platformBadge, act, emptyState, errorState, skeleton, confirmDialog, toast, fmtDateTime, fmtRel, titleCase, PLATFORMS, PLATFORM_LABEL } from '../ui.js';
import { pageHead, card, kv, toggle, field, logList } from '../comp.js';

export default async function page(ctx) {
  const S = { d: null, form: null, formDirty: false, alive: true };
  ctx.setDirty(() => S.formDirty);
  const controlBox = h('div'), settingsBox = h('div'), todayBox = h('div'), histBox = h('div'), logBox = h('div');
  const root = h('div', { class: 'stack' }, controlBox, h('div', { class: 'grid cols-2' }, card('Schedule & settings', settingsBox), card("Today's picks", todayBox)), card('Run history', histBox), card('Live automation logs', logBox, { sub: 'Refreshes every 5 seconds.' }));
  ctx.root.append(pageHead('Automation', 'Daily autonomous recaps: three distinct titles, one per enabled platform, started at the scheduled time (Asia/Bangkok).'), root);

  /* ---------- controls ---------- */
  async function control(action, btn) {
    if (action === 'stop') {
      const ok = await confirmDialog({ title: 'Stop automation?', message: 'The scheduler stops. Jobs already running continue; nothing new starts until you press Start again.', confirmText: 'Stop automation' });
      if (!ok) return;
    }
    const d = await act(() => api.post(`/api/automation/${action}`, {}), { btn, ok: `Automation ${action === 'start' ? 'started' : action === 'pause' ? 'paused' : action === 'resume' ? 'resumed' : 'stopped'}` });
    if (d) { S.d = d; drawDynamic(); }
  }
  async function runNow(btn) {
    const ok = await confirmDialog({ title: 'Run now?', message: 'Starts today’s automatic run immediately: three titles are picked and their pipelines are queued. Running again the same day returns the existing run instead of starting a second one.', confirmText: 'Run now', danger: false });
    if (!ok) return;
    const r = await act(() => api.post('/api/automation/run-now', {}), { btn });
    if (!r) return;
    toast(r.already_ran_today ? `Automation already ran today. Showing existing job #${r.job?.id ?? '?'}; nothing new was started.` : `Run started (job #${r.job?.id ?? '?'}).`, r.already_ran_today ? 'info' : 'ok');
    refresh();
  }

  function drawControls() {
    const d = S.d, st = d.state;
    const big = (action, label, ic, enabled, cls = '') => h('button', { class: `btn lg ctrl-big ${cls}`, write: true, disabled: !enabled || undefined, 'aria-label': label, onclick: (e) => control(action, e.currentTarget) }, icon(ic, 22), label);
    controlBox.replaceChildren(card(null, h('div', { class: 'stack' },
      h('div', { class: 'row between' }, h('div', { class: 'row' }, h('span', { class: `dot ${st === 'running' ? 'ok' : st === 'paused' ? 'warn' : 'err'}` }), h('h2', { class: 'state-h', 'aria-live': 'polite' }, `Automation is ${st}`), statusBadge(st)),
        h('div', { class: 'row' }, badge(d.workers?.running ? `Workers running (${d.workers.threads ?? '?'} threads)` : 'Workers stopped', d.workers?.running ? 'ok' : 'err'))),
      h('div', { class: 'ctrl-row' }, big('start', 'Start', 'play', st === 'stopped', 'primary'), big('pause', 'Pause', 'pause', st === 'running'), big('resume', 'Resume', 'play', st === 'paused', 'blue'), big('stop', 'Stop', 'stop', st !== 'stopped', 'danger-ghost')),
      h('div', { class: 'grid cols-4 keep2' },
        h('div', {}, h('p', { class: 'lbl-s' }, 'Schedule'), h('b', {}, `${d.schedule || '—'} ICT`)), h('div', {}, h('p', { class: 'lbl-s' }, 'Next run'), h('b', {}, fmtDateTime(d.next_run))),
        h('div', {}, h('p', { class: 'lbl-s' }, 'Last run date'), h('b', {}, d.last_run_date || 'Never')), h('div', {}, h('p', { class: 'lbl-s' }, 'Publish mode'), h('b', {}, titleCase(d.publish_mode || '—')))),
      h('div', { class: 'row' }, h('button', { class: 'btn', write: true, onclick: (e) => runNow(e.currentTarget) }, icon('zap', 16), 'Run now'), h('span', { class: 'muted sm' }, 'Idempotent: a second press on the same day returns the existing run.')))));
  }

  /* ---------- settings form ---------- */
  function drawSettings() {
    const d = S.d;
    const mark = () => { S.formDirty = true; saveBtn.disabled = !ctx.canWrite; dirtyEl.replaceChildren(badge('Unsaved changes', 'warn')); };
    const sched = h('input', { type: 'time', id: 'sch', step: 60, value: d.schedule || '', write: true, oninput: mark });
    const plats = Object.fromEntries(PLATFORMS.map((p) => [p, !!d.platforms?.[p]]));
    const pm = h('select', { id: 'pm', write: true, onchange: mark }, h('option', { value: 'draft' }, 'Draft (manual publish)'), h('option', { value: 'auto' }, 'Auto publish (API)')); pm.value = d.publish_mode || 'draft';
    const att = h('input', { type: 'number', id: 'att', min: 1, max: 10, step: 1, value: d.retry?.max_attempts ?? '', write: true, oninput: mark });
    const bo = h('input', { type: 'number', id: 'bo', min: 0, step: 1, value: d.retry?.backoff_s ?? '', write: true, oninput: mark });
    const mf = h('input', { type: 'number', id: 'mf', min: 0, step: 0.5, value: d.storage?.min_free_gb ?? '', write: true, oninput: mark });
    const err = h('p', { class: 'txt-err sm', role: 'alert' });
    const dirtyEl = h('span', {}, badge('Saved', 'ok'));
    const saveBtn = h('button', { class: 'btn primary', write: true, disabled: true, onclick: async (e) => {
      err.textContent = '';
      if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(sched.value)) { err.textContent = 'Schedule must be a valid HH:MM time.'; return; }
      if (!Object.values(plats).some(Boolean)) { err.textContent = 'Enable at least one platform.'; return; }
      const a = Number(att.value), b = Number(bo.value), m = Number(mf.value);
      if (!Number.isInteger(a) || a < 1) { err.textContent = 'Max attempts must be a whole number of at least 1.'; return; }
      if (!isFinite(b) || b < 0) { err.textContent = 'Backoff must be 0 seconds or more.'; return; }
      if (!isFinite(m) || m < 0 || mf.value === '') { err.textContent = 'Minimum free disk must be 0 GB or more.'; return; }
      const r = await act(() => api.put('/api/automation/settings', { schedule: sched.value, platforms: plats, publish_mode: pm.value, retry: { max_attempts: a, backoff_s: b }, storage: { min_free_gb: m } }), { btn: e.currentTarget, ok: 'Automation settings saved' });
      if (r) { S.d = r; S.formDirty = false; drawAll(); }
    } }, icon('save', 16), 'Save settings');
    settingsBox.replaceChildren(h('div', { class: 'stack' },
      h('div', { class: 'form-grid' }, field('Daily start time (Asia/Bangkok, HH:MM)', sched, 'Time of day in ICT (UTC+7).'), field('Publish mode', pm, 'Auto publishes through the platform API only when it is configured; otherwise a draft is prepared.'),
        field('Max attempts per stage', att), field('Retry backoff (seconds)', bo), field('Minimum free disk (GB)', mf, 'Runs are skipped below this free space.')),
      h('div', { class: 'field' }, h('span', { class: 'lbl-s' }, 'Platforms in the daily run'), h('div', { class: 'row' }, PLATFORMS.map((p) => toggle(plats[p], (v) => { plats[p] = v; mark(); }, PLATFORM_LABEL[p])))),
      err, h('div', { class: 'row' }, saveBtn, dirtyEl)));
  }

  /* ---------- dynamic parts ---------- */
  function drawToday() {
    const t = S.d.today || {};
    const picks = t.picks || [], projects = t.projects || [];
    todayBox.replaceChildren(picks.length ? h('div', { class: 'stack sm' }, h('p', { class: 'muted sm' }, t.date || ''), picks.map((p) => {
      const proj = p.project_id ? projects.find((x) => x.id === p.project_id) : null;
      return h('div', { class: 'pick' }, h('div', { class: 'row between' }, platformBadge(p.platform), proj ? statusBadge(proj.status) : badge(p.category || '—', 'muted')), h('b', {}, p.title),
        proj ? h('div', { class: 'job-prog' }, h('span', { class: 'muted sm' }, `${Math.round(proj.progress || 0)}%${proj.stage ? ' · ' + proj.stage : ''}`)) : null,
        p.project_id ? h('a', { class: 'sm', href: `#/renderer?project=${p.project_id}` }, `Project #${p.project_id} →`) : h('span', { class: 'muted sm' }, 'Project not created yet'));
    })) : emptyState({ icon: 'star', title: 'No picks yet today', text: 'Picks appear when the daily run starts.' }));
  }
  function drawHistory() {
    const hist = S.d.history || [];
    histBox.replaceChildren(hist.length ? h('div', {}, hist.map((r) => h('div', { class: 'hist-item' }, h('div', { class: 'row between' }, h('b', {}, r.date), statusBadge(r.status)),
      (r.projects || []).length ? h('div', { class: 'stack sm' }, r.projects.map((p) => h('div', { class: 'row' }, platformBadge(p.platform), h('span', { class: 'grow' }, p.title), statusBadge(p.status), p.project_id ? h('a', { class: 'sm', href: `#/projects?project=${p.project_id}` }, `#${p.project_id}`) : null)))
        : h('p', { class: 'muted sm' }, 'No projects recorded for this run.')))) : emptyState({ icon: 'clock', title: 'No runs yet', text: 'Past daily runs will be listed here.' }));
  }
  function drawDynamic() { drawControls(); drawToday(); drawHistory(); }
  function drawAll() { drawDynamic(); drawSettings(); }

  async function refresh() {
    try {
      const d = await api.get('/api/automation');
      if (!S.alive) return;
      const first = !S.d; S.d = d;
      if (first) drawAll(); else { drawDynamic(); if (!S.formDirty) drawSettings(); }
    } catch (e) { if (!S.d && e.status !== 401) root.replaceChildren(errorState(e, async () => { root.replaceChildren(skeleton('rows', 4)); location.reload(); })); }
  }
  let lSig = '';
  async function refreshLogs() {
    try {
      const d = await api.get('/api/automation/logs', { limit: 100 });
      const sig = JSON.stringify(d); if (sig === lSig) return; lSig = sig;
      logBox.replaceChildren(logList(d.logs, { empty: 'No automation log entries yet.' }));
    } catch (e) { if (!lSig) logBox.replaceChildren(errorState(e, refreshLogs)); }
  }
  controlBox.append(skeleton('rows', 3));
  await Promise.all([refresh(), refreshLogs()]);
  ctx.poll.add(() => Promise.all([refresh(), refreshLogs()]), 5000);
  return { destroy() { S.alive = false; } };
}
